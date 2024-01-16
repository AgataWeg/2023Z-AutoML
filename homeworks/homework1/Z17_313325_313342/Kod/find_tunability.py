import argparse
import os
import pickle
import warnings
from collections import defaultdict

import numpy as np
import openml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from tqdm import tqdm
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

np.random.seed(42)

HYPERPARAMETERS_SPACE_RFC = {
    "n_estimators": list(range(1, 200)),
    "max_depth": [None] + list(range(10, 51)),
    "min_samples_split": list(range(2, 21)),
    "min_samples_leaf": list(range(1, 11)),
    "max_features": np.random.uniform(0.1, 1, 100),
    "bootstrap": [True],
    "criterion": ["gini", "entropy"],
    "class_weight": [None, "balanced"],
    "max_samples": np.random.uniform(0.1, 1, 100),
}

HYPERPARAMETERS_SPACE_XGB = {
    "n_estimators": np.arange(1, 150),
    "max_depth": np.arange(1, 15),
    "learning_rate": np.random.uniform(0, 1, 100),
    "booster": ["gbtree", "gblinear", "dart"],
    "gamma": np.random.uniform(0.001, 1024, 1000),
    "subsumple": np.random.uniform(0.1, 1, 10),
    "colsample_bytree": np.random.uniform(0, 1, 10),
    "colsample_bylevel": np.random.uniform(0, 1, 10),
    "reg_alpha": np.random.uniform(0.001, 1024, 1000),
    "reg_lambda": np.random.uniform(0.001, 1024, 1000),
}

HYPERPARAMETERS_SPACE_TREE = {
    "criterion": ["gini", "entropy"],
    "splitter": ["best", "random"],
    "max_depth": np.arange(1, 30),
    "min_samples_split": np.arange(2, 30),
    "min_samples_leaf": np.arange(1, 30),
    "max_features": np.random.uniform(0.1, 1, 100),
}

labels = {44: "class", 1504: "Class", 37: "class", 1494: "Class"}


def prepare_data(dataset_number):
    dataset = openml.datasets.get_dataset(dataset_number)
    df = dataset.get_data()[0]
    df[labels[dataset_number]] = np.where(
        df[labels[dataset_number]] == df[labels[dataset_number]].cat.categories[0], 0, 1
    )
    train, test = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df[labels[dataset_number]]
    )

    X_train = train.drop(labels[dataset_number], axis=1)
    y_train = train[labels[dataset_number]]
    X_test = test.drop(labels[dataset_number], axis=1)
    y_test = test[labels[dataset_number]]

    return X_train, y_train, X_test, y_test


def main(args):
    model = args.model
    print("Model: ", model)
    with open(
        f"../Wyniki/best_default_models/best_hparams_auc_{model}.pickle", "rb"
    ) as handle:
        best_hparams_auc = pickle.load(handle)

    default_auc_values = {}
    for dataset_number in labels.keys():
        X_train, y_train, X_test, y_test = prepare_data(dataset_number)

        if model == "RFC":
            clf = RandomForestClassifier(**best_hparams_auc, random_state=42)
        elif model == "XGB":
            clf = XGBClassifier(**best_hparams_auc, random_state=42)
        elif model == "TREE":
            clf = DecisionTreeClassifier(**best_hparams_auc, random_state=42)

        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)
        default_auc_values[dataset_number] = roc_auc_score(y_test, y_pred)

    print("Default AUC values: ", default_auc_values)

    hyperparams_tunability = defaultdict(list)
    for hyperparam in best_hparams_auc.keys():
        print("Hyperparameter: ", hyperparam)

        if model == "RFC":
            no_iters = int(
                np.ceil(len(HYPERPARAMETERS_SPACE_RFC[hyperparam]) * len(labels) * 0.8)
            )
        elif model == "XGB":
            no_iters = int(
                np.ceil(len(HYPERPARAMETERS_SPACE_XGB[hyperparam]) * len(labels) * 0.8)
            )
        elif model == "TREE":
            no_iters = int(
                np.ceil(len(HYPERPARAMETERS_SPACE_TREE[hyperparam]) * len(labels) * 0.8)
            )
        else:
            raise ValueError("Model not supported")

        for _ in tqdm(range(no_iters)):
            dataset_number = int(np.random.choice(list(labels.keys())))
            X_train, y_train, X_test, y_test = prepare_data(dataset_number)

            if model == "RFC":
                new_hyperparam_value = np.random.choice(
                    HYPERPARAMETERS_SPACE_RFC[hyperparam]
                )
                best_hparams_copy = best_hparams_auc.copy()
                best_hparams_copy[hyperparam] = new_hyperparam_value
                clf = RandomForestClassifier(**best_hparams_copy, random_state=42)
            elif model == "XGB":
                new_hyperparam_value = np.random.choice(
                    HYPERPARAMETERS_SPACE_XGB[hyperparam]
                )
                best_hparams_copy = best_hparams_auc.copy()
                best_hparams_copy[hyperparam] = new_hyperparam_value
                clf = XGBClassifier(**best_hparams_copy, random_state=42)
            elif model == "TREE":
                new_hyperparam_value = np.random.choice(
                    HYPERPARAMETERS_SPACE_TREE[hyperparam]
                )
                best_hparams_copy = best_hparams_auc.copy()
                best_hparams_copy[hyperparam] = new_hyperparam_value
                clf = DecisionTreeClassifier(**best_hparams_copy, random_state=42)

            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            new_auc = roc_auc_score(y_test, y_pred)

            difference = new_auc - default_auc_values[dataset_number]
            hyperparams_tunability[hyperparam].append(difference)

        path_to_save = f"../Wyniki/tunability/{model}/random_search"

        if not os.path.exists(path_to_save):
            os.makedirs(path_to_save)

        for hyperparam in hyperparams_tunability.keys():
            file_name = f"{model}_{hyperparam}_tunability.pickle"
            with open(os.path.join(path_to_save, file_name), "wb") as handle:
                pickle.dump(hyperparams_tunability[hyperparam], handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="XGB")
    args = parser.parse_args()
    main(args)

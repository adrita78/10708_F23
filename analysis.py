import torch
from tqdm import tqdm
import numpy as np
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt
from scipy.stats import fisher_exact


def get_confusion_matrix(model, dataloader, device, save, fname=None):
    model.eval()

    y_true = []
    y_pred = []

    for batch in tqdm(dataloader):
        inputs = batch['input_ids'].to(device)
        #attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels']

        with torch.inference_mode():
            logits = model(inputs, attention_mask).squeeze()

        preds = torch.where(logits > 0.5, 1, 0)
        y_pred.extend(preds.cpu().tolist())
        y_true.extend(labels.tolist())

    if save:
        ConfusionMatrixDisplay.from_predictions(y_true=y_true, y_pred=y_pred)
        plt.title(fname)
        plt.savefig(f'./graphics/{fname}.png')

    return confusion_matrix(y_true=y_true, y_pred=y_pred)

def fisher_test(matrix):
    return fisher_exact(table=matrix, alternative='two-sided').pvalue

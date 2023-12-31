import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm
from sklearn.metrics import accuracy_score


class JointModel(nn.Module):
    def __init__(self, gnn_model, protbert_model, projection_dim):
        super(JointModel, self).__init__()
        self.gnn_model = gnn_model
        self.protbert_model = protbert_model
        self.projection_dim = projection_dim
        self.projection_layer = nn.Linear(gnn_model.output_dim + protbert_model.config.hidden_size, projection_dim)
        self.fc = nn.Linear(projection_dim, 1)

    def forward(self, gnn_input, protbert_input):
        gnn_output = self.gnn_model(gnn_input)
        protbert_output = self.protbert_model(**protbert_input)
        combined_output = torch.cat((gnn_output, protbert_output.last_hidden_state[:, 0, :]), dim=1)
        projected_output = self.projection_layer(combined_output)
        logits = self.fc(projected_output)
        return logits

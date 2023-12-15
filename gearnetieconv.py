
from collections.abc import Sequence

import torch
from torch import nn
from torch.nn import functional as F

from torch_scatter import scatter_add

from torchdrug import core, layers
from torchdrug.core import Registry as R
from torchdrug import data

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils.rnn import pad_sequence


class GearNetIEConv(nn.Module, core.Configurable):

    def __init__(self, input_dim, embedding_dim, hidden_dims, num_relation, edge_input_dim=None,
                 batch_norm=False, activation="relu", concat_hidden=False, short_cut=True,
                 readout="sum", dropout=0, num_angle_bin=None, layer_norm=False, use_ieconv=False):
        super(GearNetIEConv, self).__init__()

        if not isinstance(hidden_dims, Sequence):
            hidden_dims = [hidden_dims]
        self.input_dim = input_dim
        self.embedding_dim = embedding_dim
        self.output_dim = sum(hidden_dims) if concat_hidden else hidden_dims[-1]
        self.dims = [embedding_dim if embedding_dim > 0 else input_dim] + list(hidden_dims)
        self.edge_dims = [edge_input_dim] + self.dims[:-1]
        self.num_relation = num_relation
        self.concat_hidden = concat_hidden
        self.short_cut = short_cut
        self.num_angle_bin = num_angle_bin
        self.short_cut = short_cut
        self.concat_hidden = concat_hidden
        self.layer_norm = layer_norm
        self.use_ieconv = use_ieconv

        if embedding_dim > 0:
            self.linear = nn.Linear(input_dim, embedding_dim)
            self.embedding_batch_norm = nn.BatchNorm1d(embedding_dim)

        self.layers = nn.ModuleList()
        self.ieconvs = nn.ModuleList()
        for i in range(len(self.dims) - 1):
            # note that these layers are from gearnet.layer instead of torchdrug.layers
            self.layers.append(GeometricRelationalGraphConv(self.dims[i], self.dims[i + 1], num_relation,
                                                                   None, batch_norm, activation))
            if use_ieconv:
                self.ieconvs.append(IEConvLayer(self.dims[i], self.dims[i] // 4,
                                    self.dims[i+1], edge_input_dim=14, kernel_hidden_dim=32))
        if num_angle_bin:
            self.spatial_line_graph = layers.SpatialLineGraph(num_angle_bin)
            self.edge_layers = nn.ModuleList()
            for i in range(len(self.edge_dims) - 1):
                self.edge_layers.append(GeometricRelationalGraphConv(
                    self.edge_dims[i], self.edge_dims[i + 1], num_angle_bin, None, batch_norm, activation))

        if layer_norm:
            self.layer_norms = nn.ModuleList()
            for i in range(len(self.dims) - 1):
                self.layer_norms.append(nn.LayerNorm(self.dims[i + 1]))

        self.dropout = nn.Dropout(dropout)

        if readout == "sum":
            self.readout = layers.SumReadout()
        elif readout == "mean":
            self.readout = layers.MeanReadout()
        else:
            raise ValueError("Unknown readout `%s`" % readout)

        self.output_layer = nn.Linear(self.output_dim, 1)
        self.sigmoid = nn.Sigmoid()

    def get_ieconv_edge_feature(self, graph):
        u = torch.ones_like(graph.node_position)
        u[1:] = graph.node_position[1:] - graph.node_position[:-1]
        u = F.normalize(u, dim=-1)
        b = torch.ones_like(graph.node_position)
        b[:-1] = u[:-1] - u[1:]
        b = F.normalize(b, dim=-1)
        n = torch.ones_like(graph.node_position)
        n[:-1] = torch.cross(u[:-1], u[1:])
        n = F.normalize(n, dim=-1)

        local_frame = torch.stack([b, n, torch.cross(b, n)], dim=-1)

        node_in, node_out = graph.edge_list.t()[:2]
        t = graph.node_position[node_out] - graph.node_position[node_in]
        t = torch.einsum('ijk, ij->ik', local_frame[node_in], t)
        r = torch.sum(local_frame[node_in] * local_frame[node_out], dim=1)
        delta = torch.abs(graph.atom2residue[node_in] - graph.atom2residue[node_out]).float() / 6
        delta = delta.unsqueeze(-1)

        return torch.cat([
            t, r, delta,
            1 - 2 * t.abs(), 1 - 2 * r.abs(), 1 - 2 * delta.abs()
        ], dim=-1)

    def forward(self, graph, input, all_loss=None, metric=None):
        hiddens = []
        layer_input = input

        if self.num_angle_bin:
            line_graph = self.spatial_line_graph(graph)
            edge_hidden = line_graph.node_feature.float()
        else:
            edge_hidden = None

        ieconv_edge_feature = self.get_ieconv_edge_feature(graph)

        for i in range(len(self.layers)):
            if self.use_ieconv:
                layer_input = self.ieconvs[i](layer_input, graph.edge_list, ieconv_edge_feature)
            else:
                layer_input = self.layers[i](layer_input, graph.edge_list)

            if self.layer_norm:
                layer_input = self.layer_norms[i](layer_input)

            layer_input = F.relu(layer_input)
            layer_input = self.dropout(layer_input)
            hiddens.append(layer_input)

        if self.concat_hidden:
            node_feature = torch.cat(hiddens, dim=-1)
        else:
            node_feature = hiddens[-1]

        output = self.output_layer(node_feature)
        output = self.sigmoid(output)

        return {
            "output": output,
            "node_feature": node_feature
        }

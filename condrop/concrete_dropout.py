import numpy as np

import torch
import torch.nn as nn
from torch import Tensor


class ConcreteDropout(nn.Module):
    """
    Concrete Dropout.

    Implementation of the Concrete Dropout module as described in the
    'Concrete Dropout' paper: https://arxiv.org/pdf/1705.07832
    """
    def __init__(
        self,
        weight_regulariser: float,
        dropout_regulariser: float,
        init_min: float = 0.1,
        init_max: float = 0.1,
        temperate: float = 0.1,
        mc_dropout: bool = False,
    ) -> None:

        """
        Concrete Dropout.

        Parameters
        ----------
        weight_regulariser : float
            Weight regulariser term.
        dropout_regulariser : float
            Dropout regulariser term.
        init_min : float
            Initial min value.
        init_max : float
            Initial max value.
        """
        super().__init__()

        self.weight_regulariser = weight_regulariser
        self.dropout_regulariser = dropout_regulariser

        init_min = np.log(init_min) - np.log(1.0 - init_min)
        init_max = np.log(init_max) - np.log(1.0 - init_max)

        self.p_logit = nn.Parameter(torch.empty(1).uniform_(init_min, init_max))
        self.p = torch.sigmoid(self.p_logit)

        self.temperature = temperate
        self.mc_dropout = mc_dropout

        self.regularisation = 0.0

    def forward(self, x: Tensor, layer: nn.Module) -> Tensor:
        """
        Calculates the forward pass.

        The regularisation term for the layer is calculated and assigned to a
        class attribute - this can later be accessed to evaluate the loss.

        Parameters
        ----------
        x : Tensor
            Input to the Concrete Dropout.
        layer : nn.Module
            Layer for which to calculate the Concrete Dropout.

        Returns
        -------
        Tensor
            Output from the dropout layer.
        """
        if self.training or self.mc_dropout:
            output = layer(self._concrete_dropout(x))
        else:
            output = layer(x)

        sum_of_squares = 0
        for param in layer.parameters():
            sum_of_squares += torch.sum(torch.pow(param, 2))

        weights_reg = self.weight_regulariser * sum_of_squares / (1.0 - self.p)

        dropout_reg = self.p * torch.log(self.p)
        dropout_reg += (1.0 - self.p) * torch.log(1.0 - self.p)
        dropout_reg *= self.dropout_regulariser * x[0].numel()

        self.regularisation = weights_reg + dropout_reg

        return output

    def _concrete_dropout(self, x: Tensor) -> Tensor:
        """
        Computes the Concrete Dropout.

        Parameters
        ----------
        x : Tensor
            Input tensor to the Concrete Dropout layer.

        Returns
        -------
        Tensor
            Outputs from Concrete Dropout.
        """
        eps = torch.finfo(x.dtype).eps
        tmp = 0.1

        self.p = torch.sigmoid(self.p_logit)
        u_noise = torch.rand_like(x)

        drop_prob = (
            torch.log(self.p + eps) -
            torch.log(1 - self.p + eps) +
            torch.log(u_noise + eps) -
            torch.log(1 - u_noise + eps)
        )

        drop_prob = torch.sigmoid(drop_prob / tmp)

        random_dropout_mask = 1.0 - drop_prob
        retain_prob = 1.0 - self.p

        x = torch.mul(x, random_dropout_mask) / retain_prob
        return x


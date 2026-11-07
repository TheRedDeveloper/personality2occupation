#!/usr/bin/env python3
"""
Custom PyTorch Module for value_final (SotirisLegkas/roberta-large_ALL_BCE_translated_data_multihead_19_shuffled_special_tokens_final).

Implements the multi-head RoBERTa-large architecture used in Step 2:
- RoBERTa-large backbone (355M params)
- 9 language classification heads ('EN', 'EL', etc.), each with 3 extra RoBERTa layers + linear projection to 19 values
- Direct multi-label BCE logits for the canonical 19 Schwartz values
"""

from typing import List, Tuple, Dict, Any, Optional
import torch
import torch.nn as nn
from transformers import RobertaModel, RobertaPreTrainedModel
from transformers.models.roberta.modeling_roberta import RobertaLayer

# Canonical 19 Schwartz values list matching Touché 2024 / ValueEval'24
VALUES = [
    "Self-direction: thought",
    "Self-direction: action",
    "Stimulation",
    "Hedonism",
    "Achievement",
    "Power: dominance",
    "Power: resources",
    "Face",
    "Security: personal",
    "Security: societal",
    "Tradition",
    "Conformity: rules",
    "Conformity: interpersonal",
    "Humility",
    "Benevolence: caring",
    "Benevolence: dependability",
    "Universalism: concern",
    "Universalism: nature",
    "Universalism: tolerance",
]


class RobertaClassificationHeadCustom(nn.Module):
    """RoBERTa-large classification head matching value_final checkpoint."""

    def __init__(self, config):
        super().__init__()
        self.extra_transformer_layer_1 = RobertaLayer(config)
        self.extra_transformer_layer_2 = RobertaLayer(config)
        self.extra_transformer_layer_3 = RobertaLayer(config)
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        classifier_dropout = (
            config.classifier_dropout
            if config.classifier_dropout is not None
            else config.hidden_dropout_prob
        )
        self.dropout = nn.Dropout(classifier_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = self.extra_transformer_layer_1(features)
        x = self.extra_transformer_layer_2(x[0])
        x = self.extra_transformer_layer_3(x[0])
        x = x[0][:, 0, :]  # CLS token
        x = self.dropout(x)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        x = self.out_proj(x)
        return x


class MultiHead_MultiLabel_Roberta(RobertaPreTrainedModel):
    """RoBERTa-large multi-head architecture for value_final."""

    _keys_to_ignore_on_load_unexpected = [r"pooler"]
    _keys_to_ignore_on_load_missing = [r"position_ids"]

    def __init__(self, config):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.roberta = RobertaModel(config, add_pooling_layer=True)
        self.language_heads = nn.ModuleDict({
            "EN": RobertaClassificationHeadCustom(config),
            "EL": RobertaClassificationHeadCustom(config),
            "DE": RobertaClassificationHeadCustom(config),
            "TR": RobertaClassificationHeadCustom(config),
            "FR": RobertaClassificationHeadCustom(config),
            "BG": RobertaClassificationHeadCustom(config),
            "HE": RobertaClassificationHeadCustom(config),
            "IT": RobertaClassificationHeadCustom(config),
            "NL": RobertaClassificationHeadCustom(config),
        })

    def forward(self, input_ids=None, attention_mask=None, language="EN"):
        """Forward pass routing arbitrary batch size to the requested language head (default English)."""
        outputs = self.roberta(input_ids, attention_mask=attention_mask)
        head = self.language_heads[language]
        logits = head(outputs.last_hidden_state)
        return logits

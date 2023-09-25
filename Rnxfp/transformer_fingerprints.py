# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02_transformer_fingerprints.ipynb (unless otherwise specified).

__all__ = ['RXNBERTFingerprintGenerator', 'RXNBERTMinhashFingerprintGenerator', 'get_default_model_and_tokenizer',
           'generate_fingerprints']


import torch
import pkg_resources
import numpy as np
from typing import List
from tqdm import tqdm
from itertools import islice


from transformers import BertModel

from core import FingerprintGenerator
from tokenization import SmilesTokenizer


# Cell
class RXNBERTFingerprintGenerator(FingerprintGenerator):
    """
    Generate RXNBERT fingerprints from reaction SMILES
    """

    def __init__(self, model: BertModel, tokenizer: SmilesTokenizer, force_no_cuda=False):
        super(RXNBERTFingerprintGenerator).__init__()
        self.model = model
        self.model.eval()
        self.tokenizer = tokenizer
        self.device = torch.device("cuda" if (torch.cuda.is_available() and not force_no_cuda) else "cpu")

    def convert(self, rxn_smiles: str):
        """
        Convert rxn_smiles to fingerprint

        Args:
            rxn_smiles (str): precursors>>products
        """
        bert_inputs = self.tokenizer.encode_plus(rxn_smiles,
                                                max_length=self.model.config.max_position_embeddings,
                                                padding=True, truncation=True, return_tensors='pt').to(self.device)

        with torch.no_grad():
            output = self.model(
                **bert_inputs
            )


        embeddings = output['last_hidden_state'].squeeze()[0].cpu().numpy().tolist()
        return embeddings

    def convert_batch(self, rxn_smiles_list: List[str]):
        bert_inputs = self.tokenizer.batch_encode_plus(rxn_smiles_list,
                                                       max_length=self.model.config.max_position_embeddings,
                                                       padding=True, truncation=True, return_tensors='pt').to(self.device)
        with torch.no_grad():
            output = self.model(
                **bert_inputs
            )


        # [CLS] token embeddings in position 0
        embeddings = output['last_hidden_state'][:, 0, :].cpu().numpy().tolist()
        return embeddings


class RXNBERTMinhashFingerprintGenerator(FingerprintGenerator):
    """
    Generate RXNBERT fingerprints from reaction SMILES
    """

    def __init__(
        self, model: BertModel, tokenizer: SmilesTokenizer, permutations=256, seed=42, force_no_cuda=False
    ):
        super(RXNBERTFingerprintGenerator).__init__()
        import tmap as tm

        self.model = model
        self.tokenizer = tokenizer
        self.minhash = tm.Minhash(model.config.hidden_size, seed, permutations)
        self.generator = RXNBERTFingerprintGenerator(model, tokenizer)
        self.device = torch.device("cuda" if (torch.cuda.is_available() and not force_no_cuda) else "cpu")

    def convert(self, rxn_smiles: str):
        """
        Convert rxn_smiles to fingerprint

        Args:
            rxn_smiles (str): precursors>>products
        """
        float_fingerprint = self.generator.convert(rxn_smiles)
        minhash_fingerprint = self.minhash.from_weight_array(
            float_fingerprint, method="I2CWS"
        )
        return minhash_fingerprint

    def convert_batch(self, rxn_smiles_list: List[str]):
        float_fingerprints = self.generator.convert_batch(rxn_smiles_list)
        minhash_fingerprints = [
            self.minhash.from_weight_array(fp, method="I2CWS")
            for fp in float_fingerprints
        ]
        return minhash_fingerprints

def get_default_model_and_tokenizer(model='bert_ft', force_no_cuda=False):

    model_path =  pkg_resources.resource_filename(
                "rxnfp",
                f"models/transformers/{model}"
            )

    tokenizer_vocab_path = (
        pkg_resources.resource_filename(
                    "rxnfp",
                    f"models/transformers/{model}/vocab.txt"
                )
    )
    device = torch.device("cuda" if (torch.cuda.is_available() and not force_no_cuda) else "cpu")

    model = BertModel.from_pretrained(model_path)
    model = model.eval()
    model.to(device)

    tokenizer = SmilesTokenizer(
        tokenizer_vocab_path
    )
    return model, tokenizer

def generate_fingerprints(rxns: List[str], fingerprint_generator:FingerprintGenerator, batch_size=1) -> np.array:
    fps = []

    n_batches = len(rxns) // batch_size
    emb_iter = iter(rxns)
    for i in tqdm(range(n_batches)):
        batch = list(islice(emb_iter, batch_size))

        fps_batch = fingerprint_generator.convert_batch(batch)

        fps += fps_batch
    return np.array(fps)
from typing import Dict, Tuple, List

import numpy as np
import torch

from utils.data.ska_dataset import SKADataSet, StaticSKATransformationDecorator
from utils.data.generating import COMMON_ATTRIBUTES, SOURCE_ATTRIBUTES


def to_float(tensors: List[torch.Tensor]): return list(map(lambda t: t.float(), tensors))

def unsqueeze(tensors: List[torch.Tensor]): return list(map(lambda t: t.unsqueeze(0), tensors))

def fill_dict(units: np.ndarray, dataset: Dict[str, np.ndarray], required_attrs: List[str]):
    split_dict = dict()
    for k, v in dataset.items():
        if k == 'index':
            split_dict[k] = len(units[units < v])
            continue
        if k == 'dim':
            split_dict[k] = v
            continue
        
        split_dict[k] = list()
        for i in units:
            if k not in required_attrs and i > dataset['index']:
                continue
            split_dict[k].append(v[i])
            
        if k not in required_attrs:
            split_dict[k].append(v[-1])
            
    return split_dict


def split(dataset: Dict, left_fraction: float, required_attrs: List[str]):
    n_units = len(dataset[required_attrs[0]])
    n_left = int(n_units * left_fraction)

    left_units = np.random.choice(n_units, size=n_left, replace=False).astype(np.int32)
    right_units = np.setdiff1d(np.arange(n_units), left_units).astype(np.int32)
    
    splits = tuple(map(np.sort, [left_units, right_units]))

    return tuple(map(lambda s: fill_dict(s, dataset, required_attrs), splits))

def add_transforms(base_dataset):
    for attr in ['image', 'segmentmap']:
        base_dataset = StaticSKATransformationDecorator(attr, to_float, base_dataset)
        base_dataset = StaticSKATransformationDecorator(attr, unsqueeze, base_dataset)
    return base_dataset


    

def merge(*datasets: Dict):
    merged = dict()
    index = 0
    
    for d in datasets:
        index += d['index']
    
    merged['index'] = index
    
    # Add source boxes
    for d in datasets:
        for k, v in d.items():
            if k == 'index':
                continue
            elif k == 'dim':
                if k not in merged.keys():
                    merged[k] = v
            else:
                if k not in merged.keys():
                    merged[k] = list()

                merged[k].extend(v[:d['index']])
    
    # Add empty boxes common attributes
    for d in datasets:
        for k, v in d.items():
            if k in COMMON_ATTRIBUTES:
                merged[k].extend(v[d['index']:])
    
    # Add dummy values for empty boxes
    # Assumed that datasets[0] has no empty boxes
    for k, v in datasets[0].items():
        if k in SOURCE_ATTRIBUTES:
            merged[k].append(v[-1])
        
    
    return merged
    
    

def train_val_split(dataset: Dict, train_fraction: float, required_attrs: List[str] = ['image', 'position']):
    train, validation = split(dataset, train_fraction, required_attrs)
    datsets = (SKADataSet(train), SKADataSet(validation, random_type=1))

    return tuple(map(add_transforms, datsets))
"""
 Copyright (c) 2022, salesforce.com, inc.
 All rights reserved.
 SPDX-License-Identifier: BSD-3-Clause
 For full license text, see the LICENSE_Lavis file in the repo root or https://opensource.org/licenses/BSD-3-Clause
"""

import argparse
import os
import random

import numpy as np
import torch
import torch.backends.cudnn as cudnn

import minigpt4.tasks as tasks
from minigpt4.common.config import Config
from minigpt4.common.dist_utils import get_rank, init_distributed_mode
from minigpt4.datasets.datasets.rec_gnndataset import GnnDataset
from minigpt4.common.logger import setup_logger
from minigpt4.common.optims import (
    LinearWarmupCosineLRScheduler,
    LinearWarmupStepLRScheduler,
)
from minigpt4.common.registry import registry
from minigpt4.common.utils import now

# imports modules for registration
from minigpt4.datasets.builders import *
from minigpt4.models import *
from minigpt4.processors import *
from minigpt4.runners import *
from minigpt4.tasks import *
from torch.distributed.elastic.multiprocessing.errors import *


def parse_args():
    parser = argparse.ArgumentParser(description="Training")

    # parser.add_argument("--cfg-path", required=True, help="path to configuration file.")
    parser.add_argument("--cfg-path", default='train_configs/minigpt4rec_pretrain_lgcn_ood_cc.yaml', help="path to configuration file.")
    parser.add_argument(
        "--options",
        nargs="+",
        help="override some settings in the used config, the key-value pair "
        "in xxx=yyy format will be merged into config file (deprecate), "
        "change to --cfg-options instead.",
    )

    args = parser.parse_args()
    # if 'LOCAL_RANK' not in os.environ:
    #     os.environ['LOCAL_RANK'] = str(args.local_rank)

    return args


def setup_seeds(config):
    seed = config.run_cfg.seed + get_rank()

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    cudnn.benchmark = False
    cudnn.deterministic = True


def get_runner_class(cfg):
    """
    Get runner class from config. Default to epoch-based runner.
    """
    runner_cls = registry.get_runner_class(cfg.run_cfg.get("runner", "rec_runner_base"))

    return runner_cls

@record
def main():
    job_id = now()

    cfg = Config(parse_args())

    init_distributed_mode(cfg.run_cfg)

    setup_seeds(cfg)
    setup_logger()

    # cfg.pretty_print()

    task = tasks.setup_task(cfg)
    datasets = task.build_datasets(cfg)
    
    data_name = list(datasets.keys())[0]
    

    gnndata = GnnDataset(cfg.model_cfg.rec_config,cfg.datasets_cfg.movie_ood.path)  
    cfg.model_cfg.rec_config.user_num =  int(gnndata.m_users)  
    cfg.model_cfg.rec_config.item_num = int(gnndata.n_items) 
    cfg.pretty_print()
    
    model = task.build_model(cfg)

    
    if cfg.model_cfg.rec_model == 'lightgcn':
        model.rec_encoder._set_graph(gnndata.Graph)
    
    runner = get_runner_class(cfg)(
        cfg=cfg, job_id=job_id, task=task, model=model, datasets=datasets
    )
    runner.train()


if __name__ == "__main__":
    main()

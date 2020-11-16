#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from mephisto.operations.hydra_config import *
import warnings

warnings.warn(
    "Imports from `mephisto.core` are going away soon. "
    "Please replace all of your imports from  mephisto.core.hydra_config "
    "to mephisto.operations.hydra_config ",
    PendingDeprecationWarning,
)
#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from omegaconf import DictConfig

from mephisto.utils.logger_core import get_logger
from . import api as prolific_api
from .api import eligibility_requirement_classes
from .api.base_api_resource import CREDENTIALS_CONFIG_DIR
from .api.base_api_resource import CREDENTIALS_CONFIG_PATH
from .api.constants import ProlificIDOption
from .api.constants import StudyAction
from .api.constants import StudyCodeType
from .api.constants import StudyCompletionOption
from .api.data_models import ParticipantGroup
from .api.data_models import Project
from .api.data_models import Study
from .api.data_models import Workspace
from .api.exceptions import ProlificException
from .prolific_requester import ProlificRequesterArgs

DEFAULT_PROLIFIC_BUDGET = 100000.0
DEFAULT_PROLIFIC_WORKSPACE_NAME = 'My Workspace'
DEFAULT_PROLIFIC_PROJECT_NAME = 'Project'

logger = get_logger(name=__name__)


def check_credentials(*args, **kwargs) -> bool:
    """Check whether API KEY is correct"""
    try:
        # Make a simple request to the API
        prolific_api.Users.me()
        return True
    except ProlificException:
        return False


def setup_credentials(
    profile_name: str, register_args: Optional[ProlificRequesterArgs],
) -> bool:
    if not os.path.exists(os.path.expanduser(CREDENTIALS_CONFIG_DIR)):
        os.mkdir(os.path.expanduser(CREDENTIALS_CONFIG_DIR))

    with open(os.path.expanduser(CREDENTIALS_CONFIG_PATH), 'w') as f:
        f.write(register_args.api_key)

    return True


def _get_eligibility_requirements(run_config_value: List[dict]) -> List[dict]:
    eligibility_requirements = []

    for conf_eligibility_requirement in run_config_value:
        name = conf_eligibility_requirement.get('name')

        if cls := getattr(eligibility_requirement_classes, name, None):
            cls_kwargs = {}
            for param_name in cls.params():
                if param_name in conf_eligibility_requirement:
                    cls_kwargs[param_name] = conf_eligibility_requirement[param_name]
            eligibility_requirements.append(cls(**cls_kwargs).to_prolific_dict())

    return eligibility_requirements


def check_balance(*args, **kwargs) -> Union[float, int]:
    """
    Checks to see if there is at least balance_needed amount in the
    requester account, returns True if the balance is greater than
    balance_needed
    """
    try:
        user = prolific_api.Users.me()
    except ProlificException:
        logger.exception(f'Could not receive a User Accound data')
        raise

    return user.available_balance or DEFAULT_PROLIFIC_BUDGET


def _find_prolific_workspace(
    client: prolific_api,
    id: Optional[str] = None,
    title: str = DEFAULT_PROLIFIC_WORKSPACE_NAME,
) -> Tuple[bool, Optional[str]]:
    """Find a Prolific Workspace by title or ID"""
    if id:
        try:
            workspace: Workspace = client.Workspaces.retrieve(id)
            return True, workspace.id
        except ProlificException:
            logger.exception(f'Could not find a workspace by id {id}')
            raise

    try:
        workspaces: List[Workspace] = client.Workspaces.list()
    except ProlificException:
        logger.exception(f'Could not find a workspace by title {title}')
        raise

    for workspace in workspaces:
        if workspace.title == title:
            return True, workspace.id

    return True, None


def find_or_create_prolific_workspace(
    client: prolific_api,
    id: Optional[str] = None,
    title: str = DEFAULT_PROLIFIC_WORKSPACE_NAME,
) -> Optional[str]:
    """Find or create a Prolific Workspace by title or ID"""
    found_workspace, workspace_id = _find_prolific_workspace(client, id, title)

    if found_workspace:
        return workspace_id

    try:
        workspace: Workspace = client.Workspaces.create(title=title)
    except ProlificException:
        logger.exception(f'Could not create a workspace with title "{title}"')
        raise

    return workspace.id if workspace else None


def _find_prolific_project(
    client: prolific_api,
    workspace_id: str,
    id: Optional[str] = None,
    title: str = DEFAULT_PROLIFIC_PROJECT_NAME,
) -> Tuple[bool, Optional[str]]:
    """Find a Prolific Project by title or ID"""
    try:
        projects: List[Project] = client.Projects.list_for_workspace(workspace_id)
    except ProlificException:
        logger.exception(f'Could not get projects for worspace "{workspace_id}"')
        raise

    for project in projects:
        if id and project.id == id:
            return True, project.id
        if project.title == title:
            return True, project.id

    return False, None


def find_or_create_prolific_project(
    client: prolific_api,
    workspace_id: str,
    id: Optional[str] = None,
    title: str = DEFAULT_PROLIFIC_PROJECT_NAME,
) -> Optional[str]:
    """Find or create a Prolific Workspace by title or ID"""
    found_project, project_id = _find_prolific_project(client, workspace_id, id, title)

    if found_project:
        return project_id

    try:
        project: Project = client.Projects.create_for_workspace(
            workspace_id=workspace_id,
            title=title,
        )
    except ProlificException:
        logger.exception(f'Could not create a project with title "{title}"')
        raise

    return project.id if project else None


def delete_qualification(client: prolific_api, id: str) -> bool:
    """
    Delete a qualification (Prolific Participant Group) by ID
    :param id: Prolific Participant Group's ID
    """
    # TODO (#1008): Implement later. There's no DELETE method for Prolific Participant Groups
    return True


def _find_qualification(
    client: prolific_api,
    prolific_project_id: str,
    qualification_name: str,
) -> Tuple[bool, Optional[str]]:
    """Find a qualification (Prolific Participant Group) by name"""
    try:
        qualifications: List[ParticipantGroup] = client.ParticipantGroups.list(
            project_id=prolific_project_id,
        )
    except ProlificException:
        logger.exception(f'Could not receive a qualifications for project "{prolific_project_id}"')
        raise

    for qualification in qualifications:
        if qualification.name == qualification_name:
            return True, qualification.id

    return True, None


def find_or_create_qualification(
    client: prolific_api,
    prolific_project_id: str,
    qualification_name: str,
    *args,
    **kwargs,
) -> Optional[str]:
    """Find or create a qualification (Prolific Participant Group) by name"""
    found_qualification, qualification_id = _find_qualification(
        client, prolific_project_id, qualification_name,
    )

    if found_qualification:
        return qualification_id

    try:
        qualification: ParticipantGroup = client.ParticipantGroups.create(
            project_id=prolific_project_id,
            name=qualification_name,
        )
    except ProlificException:
        logger.exception(
            f'Could not create a qualification '
            f'for project "{prolific_project_id}" with name "{qualification_name}"'
        )
        raise

    return qualification.id if qualification else None


def create_task(
    client: prolific_api, run_config: "DictConfig", prolific_project_id: str, *args, **kwargs,
) -> str:
    """Create a task (Prolific Study)"""
    # Task info
    name = run_config.task.task_title
    description = run_config.task.task_description
    # How much are you going to pay the participants in cents. We use the currency of your account.
    reward = run_config.task.task_reward

    # Provider-specific info
    total_available_places = run_config.provider.prolific_total_available_places
    estimated_completion_time_in_minutes = (
        run_config.provider.prolific_estimated_completion_time_in_minutes
    )
    external_study_url = run_config.provider.prolific_external_study_url
    prolific_id_option = run_config.provider.prolific_id_option
    eligibility_requirements = _get_eligibility_requirements(
        run_config.provider.prolific_eligibility_requirements,
    )
    completion_codes = [dict(
        code='ABC123',  # TODO (#1008): Change value
        code_type=StudyCodeType.OTHER,  # TODO (#1008): Change value
        actions=[dict(
            action=StudyAction.AUTOMATICALLY_APPROVE,  # TODO (#1008): Change value
        )],
    )]

    try:
        # TODO (#1008): Make sure that all parameters are correct
        study: Study = client.Studies.create(
            project=prolific_project_id,
            name=name,
            internal_name=name,
            description=description,
            external_study_url=external_study_url,
            prolific_id_option=prolific_id_option,
            completion_option=StudyCompletionOption.CODE,
            completion_codes=completion_codes,
            total_available_places=total_available_places,
            estimated_completion_time=estimated_completion_time_in_minutes,
            reward=reward,
            eligibility_requirements=eligibility_requirements,
        )
    except ProlificException:
        logger.exception(
            f'Could not create a Study with name "{name}" and instructions "{description}"'
        )
        raise

    study_id = study.id
    return study_id


def give_worker_qualification(
    client: prolific_api, worker_id: str, qualification_id: str, *args, **kwargs,
) -> None:
    """Give a qualification to the given worker"""
    try:
        client.ParticipantGroups.add_perticipants_to_group(
            id=qualification_id, participant_ids=[worker_id],
        )
    except ProlificException:
        logger.exception(
            f'Could not add worker {worker_id} to a qualification "{qualification_id}"'
        )
        raise


def remove_worker_qualification(
    client: prolific_api, worker_id: str, qualification_id: str, *args, **kwargs,
) -> None:
    """Remove a qualification for the given worker"""
    try:
        client.ParticipantGroups.remove_perticipants_from_group(
            id=qualification_id, participant_ids=[worker_id],
        )
    except ProlificException:
        logger.exception(
            f'Could not remove worker {worker_id} from a qualification "{qualification_id}"'
        )
        raise

# -*- encoding: utf-8 -*-
# Copyright 2013 Red Hat, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An :ref:`Action Plan <action_plan_definition>` is a flow of
:ref:`Actions <action_definition>` that should be executed in order to satisfy
a given :ref:`Goal <goal_definition>`.

An :ref:`Action Plan <action_plan_definition>` is generated by Watcher when an
:ref:`Audit <audit_definition>` is successful which implies that the
:ref:`Strategy <strategy_definition>`
which was used has found a :ref:`Solution <solution_definition>` to achieve the
:ref:`Goal <goal_definition>` of this :ref:`Audit <audit_definition>`.

In the default implementation of Watcher, an
:ref:`Action Plan <action_plan_definition>`
is only composed of successive :ref:`Actions <action_definition>`
(i.e., a Workflow of :ref:`Actions <action_definition>` belonging to a unique
branch).

However, Watcher provides abstract interfaces for many of its components,
allowing other implementations to generate and handle more complex
:ref:`Action Plan(s) <action_plan_definition>`
composed of two types of Action Item(s):

-  simple :ref:`Actions <action_definition>`: atomic tasks, which means it
   can not be split into smaller tasks or commands from an OpenStack point of
   view.
-  composite Actions: which are composed of several simple
   :ref:`Actions <action_definition>`
   ordered in sequential and/or parallel flows.

An :ref:`Action Plan <action_plan_definition>` may be described using
standard workflow model description formats such as
`Business Process Model and Notation 2.0 (BPMN 2.0) <http://www.omg.org/spec/BPMN/2.0/>`_
or `Unified Modeling Language (UML) <http://www.uml.org/>`_.

An :ref:`Action Plan <action_plan_definition>` has a life-cycle and its current
state may be one of the following:

-  **RECOMMENDED** : the :ref:`Action Plan <action_plan_definition>` is waiting
   for a validation from the :ref:`Administrator <administrator_definition>`
-  **ONGOING** : the :ref:`Action Plan <action_plan_definition>` is currently
   being processed by the :ref:`Watcher Applier <watcher_applier_definition>`
-  **SUCCEEDED** : the :ref:`Action Plan <action_plan_definition>` has been
   executed successfully (i.e. all :ref:`Actions <action_definition>` that it
   contains have been executed successfully)
-  **FAILED** : an error occured while executing the
   :ref:`Action Plan <action_plan_definition>`
-  **DELETED** : the :ref:`Action Plan <action_plan_definition>` is still
   stored in the :ref:`Watcher database <watcher_database_definition>` but is
   not returned any more through the Watcher APIs.
-  **CANCELLED** : the :ref:`Action Plan <action_plan_definition>` was in
   **PENDING** or **ONGOING** state and was cancelled by the
   :ref:`Administrator <administrator_definition>`
"""  # noqa

import datetime

import pecan
from pecan import rest
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from watcher._i18n import _
from watcher.api.controllers import base
from watcher.api.controllers import link
from watcher.api.controllers.v1 import collection
from watcher.api.controllers.v1 import types
from watcher.api.controllers.v1 import utils as api_utils
from watcher.applier import rpcapi
from watcher.common import exception
from watcher import objects
from watcher.objects import action_plan as ap_objects


class ActionPlanPatchType(types.JsonPatchType):

    @staticmethod
    def _validate_state(patch):
        serialized_patch = {'path': patch.path, 'op': patch.op}
        if patch.value is not wsme.Unset:
            serialized_patch['value'] = patch.value
        # todo: use state machines to handle state transitions
        state_value = patch.value
        if state_value and not hasattr(ap_objects.State, state_value):
            msg = _("Invalid state: %(state)s")
            raise exception.PatchError(
                patch=serialized_patch, reason=msg % dict(state=state_value))

    @staticmethod
    def validate(patch):
        if patch.path == "/state":
            ActionPlanPatchType._validate_state(patch)
        return types.JsonPatchType.validate(patch)

    @staticmethod
    def internal_attrs():
        return types.JsonPatchType.internal_attrs()

    @staticmethod
    def mandatory_attrs():
        return ["audit_id", "state", "first_action_id"]


class ActionPlan(base.APIBase):
    """API representation of a action plan.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation of an
    action plan.
    """

    _audit_uuid = None
    _first_action_uuid = None

    def _get_audit_uuid(self):
        return self._audit_uuid

    def _set_audit_uuid(self, value):
        if value == wtypes.Unset:
            self._audit_uuid = wtypes.Unset
        elif value and self._audit_uuid != value:
            try:
                audit = objects.Audit.get(pecan.request.context, value)
                self._audit_uuid = audit.uuid
                self.audit_id = audit.id
            except exception.AuditNotFound:
                self._audit_uuid = None

    def _get_first_action_uuid(self):
        return self._first_action_uuid

    def _set_first_action_uuid(self, value):
        if value == wtypes.Unset:
            self._first_action_uuid = wtypes.Unset
        elif value and self._first_action_uuid != value:
            try:
                first_action = objects.Action.get(pecan.request.context,
                                                  value)
                self._first_action_uuid = first_action.uuid
                self.first_action_id = first_action.id
            except exception.ActionNotFound:
                self._first_action_uuid = None

    uuid = types.uuid
    """Unique UUID for this action plan"""

    first_action_uuid = wsme.wsproperty(
        types.uuid, _get_first_action_uuid, _set_first_action_uuid,
        mandatory=True)
    """The UUID of the first action this action plans links to"""

    audit_uuid = wsme.wsproperty(types.uuid, _get_audit_uuid, _set_audit_uuid,
                                 mandatory=True)
    """The UUID of the audit this port belongs to"""

    state = wtypes.text
    """This action plan state"""

    links = wsme.wsattr([link.Link], readonly=True)
    """A list containing a self link and associated action links"""

    def __init__(self, **kwargs):
        super(ActionPlan, self).__init__()

        self.fields = []
        fields = list(objects.ActionPlan.fields)
        for field in fields:
            # Skip fields we do not expose.
            if not hasattr(self, field):
                continue
            self.fields.append(field)
            setattr(self, field, kwargs.get(field, wtypes.Unset))

        self.fields.append('audit_uuid')
        self.fields.append('first_action_uuid')

        setattr(self, 'audit_uuid', kwargs.get('audit_id', wtypes.Unset))
        setattr(self, 'first_action_uuid',
                kwargs.get('first_action_id', wtypes.Unset))

    @staticmethod
    def _convert_with_links(action_plan, url, expand=True):
        if not expand:
            action_plan.unset_fields_except(
                ['uuid', 'state', 'updated_at',
                 'audit_uuid', 'first_action_uuid'])

        action_plan.links = [link.Link.make_link(
            'self', url,
            'action_plans', action_plan.uuid),
            link.Link.make_link(
                'bookmark', url,
                'action_plans', action_plan.uuid,
                bookmark=True)]
        return action_plan

    @classmethod
    def convert_with_links(cls, rpc_action_plan, expand=True):
        action_plan = ActionPlan(**rpc_action_plan.as_dict())
        return cls._convert_with_links(action_plan, pecan.request.host_url,
                                       expand)

    @classmethod
    def sample(cls, expand=True):
        sample = cls(uuid='9ef4d84c-41e8-4418-9220-ce55be0436af',
                     state='ONGOING',
                     created_at=datetime.datetime.utcnow(),
                     deleted_at=None,
                     updated_at=datetime.datetime.utcnow())
        sample._first_action_uuid = '57eaf9ab-5aaa-4f7e-bdf7-9a140ac7a720'
        sample._audit_uuid = 'abcee106-14d3-4515-b744-5a26885cf6f6'
        return cls._convert_with_links(sample, 'http://localhost:9322', expand)


class ActionPlanCollection(collection.Collection):
    """API representation of a collection of action_plans."""

    action_plans = [ActionPlan]
    """A list containing action_plans objects"""

    def __init__(self, **kwargs):
        self._type = 'action_plans'

    @staticmethod
    def convert_with_links(rpc_action_plans, limit, url=None, expand=False,
                           **kwargs):
        collection = ActionPlanCollection()
        collection.action_plans = [ActionPlan.convert_with_links(
            p, expand) for p in rpc_action_plans]

        if 'sort_key' in kwargs:
            reverse = False
            if kwargs['sort_key'] == 'audit_uuid':
                if 'sort_dir' in kwargs:
                    reverse = True if kwargs['sort_dir'] == 'desc' else False
                collection.action_plans = sorted(
                    collection.action_plans,
                    key=lambda action_plan: action_plan.audit_uuid,
                    reverse=reverse)

        collection.next = collection.get_next(limit, url=url, **kwargs)
        return collection

    @classmethod
    def sample(cls):
        sample = cls()
        sample.action_plans = [ActionPlan.sample(expand=False)]
        return sample


class ActionPlansController(rest.RestController):
    """REST controller for Actions."""
    def __init__(self):
        super(ActionPlansController, self).__init__()

    from_actionsPlans = False
    """A flag to indicate if the requests to this controller are coming
    from the top-level resource ActionPlan."""

    _custom_actions = {
        'detail': ['GET'],
    }

    def _get_action_plans_collection(self, marker, limit,
                                     sort_key, sort_dir, expand=False,
                                     resource_url=None, audit_uuid=None):

        limit = api_utils.validate_limit(limit)
        sort_dir = api_utils.validate_sort_dir(sort_dir)

        marker_obj = None
        if marker:
            marker_obj = objects.ActionPlan.get_by_uuid(
                pecan.request.context, marker)

        filters = {}
        if audit_uuid:
            filters['audit_uuid'] = audit_uuid

        if sort_key == 'audit_uuid':
            sort_db_key = None
        else:
            sort_db_key = sort_key

        action_plans = objects.ActionPlan.list(
            pecan.request.context,
            limit,
            marker_obj, sort_key=sort_db_key,
            sort_dir=sort_dir, filters=filters)

        return ActionPlanCollection.convert_with_links(
            action_plans, limit,
            url=resource_url,
            expand=expand,
            sort_key=sort_key,
            sort_dir=sort_dir)

    @wsme_pecan.wsexpose(ActionPlanCollection, types.uuid, int, wtypes.text,
                         wtypes.text, types.uuid)
    def get_all(self, marker=None, limit=None,
                sort_key='id', sort_dir='asc', audit_uuid=None):
        """Retrieve a list of action plans.

        :param marker: pagination marker for large data sets.
        :param limit: maximum number of resources to return in a single result.
        :param sort_key: column to sort results by. Default: id.
        :param sort_dir: direction to sort. "asc" or "desc". Default: asc.
        :param audit_uuid: Optional UUID of an audit, to get only actions
            for that audit.
        """
        return self._get_action_plans_collection(
            marker, limit, sort_key, sort_dir, audit_uuid=audit_uuid)

    @wsme_pecan.wsexpose(ActionPlanCollection, types.uuid, int, wtypes.text,
                         wtypes.text, types.uuid)
    def detail(self, marker=None, limit=None,
               sort_key='id', sort_dir='asc', audit_uuid=None):
        """Retrieve a list of action_plans with detail.

        :param marker: pagination marker for large data sets.
        :param limit: maximum number of resources to return in a single result.
        :param sort_key: column to sort results by. Default: id.
        :param sort_dir: direction to sort. "asc" or "desc". Default: asc.
        :param audit_uuid: Optional UUID of an audit, to get only actions
            for that audit.
        """
        # NOTE(lucasagomes): /detail should only work agaist collections
        parent = pecan.request.path.split('/')[:-1][-1]
        if parent != "action_plans":
            raise exception.HTTPNotFound

        expand = True
        resource_url = '/'.join(['action_plans', 'detail'])
        return self._get_action_plans_collection(
            marker, limit,
            sort_key, sort_dir, expand,
            resource_url, audit_uuid=audit_uuid)

    @wsme_pecan.wsexpose(ActionPlan, types.uuid)
    def get_one(self, action_plan_uuid):
        """Retrieve information about the given action plan.

        :param action_plan_uuid: UUID of a action plan.
        """
        if self.from_actionsPlans:
            raise exception.OperationNotPermitted

        action_plan = objects.ActionPlan.get_by_uuid(
            pecan.request.context, action_plan_uuid)
        return ActionPlan.convert_with_links(action_plan)

    @wsme_pecan.wsexpose(None, types.uuid, status_code=204)
    def delete(self, action_plan_uuid):
        """Delete an action plan.

        :param action_plan_uuid: UUID of a action.
        """

        action_plan_to_delete = objects.ActionPlan.get_by_uuid(
            pecan.request.context,
            action_plan_uuid)
        action_plan_to_delete.soft_delete()

    @wsme.validate(types.uuid, [ActionPlanPatchType])
    @wsme_pecan.wsexpose(ActionPlan, types.uuid,
                         body=[ActionPlanPatchType])
    def patch(self, action_plan_uuid, patch):
        """Update an existing action plan.

        :param action_plan_uuid: UUID of a action plan.
        :param patch: a json PATCH document to apply to this action plan.
        """
        launch_action_plan = True
        if self.from_actionsPlans:
            raise exception.OperationNotPermitted

        action_plan_to_update = objects.ActionPlan.get_by_uuid(
            pecan.request.context,
            action_plan_uuid)
        try:
            action_plan_dict = action_plan_to_update.as_dict()
            action_plan = ActionPlan(**api_utils.apply_jsonpatch(
                action_plan_dict, patch))
        except api_utils.JSONPATCH_EXCEPTIONS as e:
            raise exception.PatchError(patch=patch, reason=e)

        launch_action_plan = False

        # transitions that are allowed via PATCH
        allowed_patch_transitions = [
            (ap_objects.State.RECOMMENDED,
             ap_objects.State.TRIGGERED),
            (ap_objects.State.RECOMMENDED,
             ap_objects.State.CANCELLED),
            (ap_objects.State.ONGOING,
             ap_objects.State.CANCELLED),
            (ap_objects.State.TRIGGERED,
             ap_objects.State.CANCELLED),
        ]

        # todo: improve this in blueprint watcher-api-validation
        if hasattr(action_plan, 'state'):
            transition = (action_plan_to_update.state, action_plan.state)
            if transition not in allowed_patch_transitions:
                error_message = _("State transition not allowed: "
                                  "(%(initial_state)s -> %(new_state)s)")
                raise exception.PatchError(
                    patch=patch,
                    reason=error_message % dict(
                        initial_state=action_plan_to_update.state,
                        new_state=action_plan.state))

            if action_plan.state == ap_objects.State.TRIGGERED:
                launch_action_plan = True

        # Update only the fields that have changed
        for field in objects.ActionPlan.fields:
            try:
                patch_val = getattr(action_plan, field)
            except AttributeError:
                # Ignore fields that aren't exposed in the API
                continue
            if patch_val == wtypes.Unset:
                patch_val = None
            if action_plan_to_update[field] != patch_val:
                action_plan_to_update[field] = patch_val

            if (field == 'state'
                    and patch_val == objects.action_plan.State.TRIGGERED):
                launch_action_plan = True

        action_plan_to_update.save()

        if launch_action_plan:
            applier_client = rpcapi.ApplierAPI()
            applier_client.launch_action_plan(pecan.request.context,
                                              action_plan.uuid)

        action_plan_to_update = objects.ActionPlan.get_by_uuid(
            pecan.request.context,
            action_plan_uuid)
        return ActionPlan.convert_with_links(action_plan_to_update)

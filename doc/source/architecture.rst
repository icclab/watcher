..
      Except where otherwise noted, this document is licensed under Creative
      Commons Attribution 3.0 License.  You can view the license at:

          https://creativecommons.org/licenses/by/3.0/

.. _architecture:

===================
System Architecture
===================


This page presents the current technical Architecture of the Watcher system.

.. _architecture_overview:

Overview
========

Below you will find a diagram, showing the main components of Watcher:

.. image:: ./images/architecture.svg
   :width: 100%


.. _components_definition:

Components
==========

.. _amqp_bus_definition:

AMQP Bus
--------

The AMQP message bus handles internal asynchronous communications between the
different Watcher components.

.. _cluster_history_db_definition:

Cluster History Database
------------------------

This component stores the data related to the
:ref:`Cluster History <cluster_history_definition>`.

It can potentially rely on any appropriate storage system (InfluxDB, OpenTSDB,
MongoDB,...) but will probably be more performant when using
`Time Series Databases <https://en.wikipedia.org/wiki/Time_series_database>`_
which are optimized for handling time series data, which are arrays of numbers
indexed by time (a datetime or a datetime range).

.. _cluster_model_db_definition:

Cluster Model Database
------------------------

This component stores the data related to the
:ref:`Cluster Data Model <cluster_data_model_definition>`.

.. _archi_watcher_api_definition:

Watcher API
-----------

This component implements the REST API provided by the Watcher system to the
external world.

It enables the :ref:`Administrator <administrator_definition>` of a
:ref:`Cluster <cluster_definition>` to control and monitor the Watcher system
via any interaction mechanism connected to this API:

-   :ref:`CLI <archi_watcher_cli_definition>`
-   Horizon plugin
-   Python SDK

You can also read the detailed description of `Watcher API`_.

.. _archi_watcher_applier_definition:

Watcher Applier
---------------

This component is in charge of executing the
:ref:`Action Plan <action_plan_definition>` built by the
:ref:`Watcher Decision Engine <watcher_decision_engine_definition>`.

It connects to the :ref:`message bus <amqp_bus_definition>` and launches the
:ref:`Action Plan <action_plan_definition>` whenever a triggering message is
received on a dedicated AMQP queue.

The triggering message contains the Action Plan UUID.

It then gets the detailed information about the
:ref:`Action Plan <action_plan_definition>` from the
:ref:`Watcher Database <watcher_database_definition>` which contains the list
of :ref:`Actions <action_definition>` to launch.

It then loops on each :ref:`Action <action_definition>`, gets the associated
class and calls the execute() method of this class.
Most of the time, this method will first request a token to the Keystone API
and if it is allowed, sends a request to the REST API of the OpenStack service
which handles this kind of :ref:`atomic Action <action_definition>`.

Note that as soon as :ref:`Watcher Applier <watcher_applier_definition>` starts
handling a given :ref:`Action <action_definition>` from the list, a
notification message is sent on the :ref:`message bus <amqp_bus_definition>`
indicating that the state of the action has changed to **ONGOING**.

If the :ref:`Action <action_definition>` is successful,
the :ref:`Watcher Applier <watcher_applier_definition>` sends a notification
message on :ref:`the bus <amqp_bus_definition>` informing the other components
of this.


If the :ref:`Action <action_definition>` fails, the
:ref:`Watcher Applier <watcher_applier_definition>` tries to rollback to the
previous state of the :ref:`Managed resource <managed_resource_definition>`
(i.e. before the command was sent to the underlying OpenStack service).

.. _archi_watcher_cli_definition:

Watcher CLI
-----------

The watcher command-line interface (CLI) can be used to interact with the
Watcher system in order to control it or to know its current status.

Please, read `the detailed documentation about Watcher CLI <https://factory.b-com.com/www/watcher/doc/python-watcherclient/>`_

.. _archi_watcher_database_definition:

Watcher Database
----------------

This database stores all the Watcher domain objects which can be requested
by the :ref:`Watcher API <archi_watcher_api_definition>` or the
:ref:`Watcher CLI <archi_watcher_cli_definition>`:

-  :ref:`Audit templates <audit_template_definition>`
-  :ref:`Audits <audit_definition>`
-  :ref:`Action plans <action_plan_definition>`
-  :ref:`Actions <action_definition>`
-  :ref:`Goals <goal_definition>`

The Watcher domain being here "*optimization of some resources provided by an
OpenStack system*".

.. _archi_watcher_decision_engine_definition:

Watcher Decision Engine
-----------------------

This component is responsible for computing a set of potential optimization
:ref:`Actions <action_definition>` in order to fulfill
the :ref:`Goal <goal_definition>` of an :ref:`Audit <audit_definition>`.

It first reads the parameters of the :ref:`Audit <audit_definition>` from the
associated :ref:`Audit Template <audit_template_definition>` and knows the
:ref:`Goal <goal_definition>` to achieve.

It then selects the most appropriate :ref:`Strategy <strategy_definition>`
depending on how Watcher was configured for this :ref:`Goal <goal_definition>`.

The :ref:`Strategy <strategy_definition>` is then dynamically loaded (via
`stevedore <https://github.com/openstack/stevedore/>`_). The
:ref:`Watcher Decision Engine <watcher_decision_engine_definition>` calls the
**execute()** method of the :ref:`Strategy <strategy_definition>` class which
generates a solution composed of a set of :ref:`Actions <action_definition>`.

These :ref:`Actions <action_definition>` are scheduled in time by the
:ref:`Watcher Planner <watcher_planner_definition>` (i.e., it generates an
:ref:`Action Plan <action_plan_definition>`).

In order to compute the potential :ref:`Solution <solution_definition>` for the
Audit, the :ref:`Strategy <strategy_definition>` relies on two sets of data:

-   the current state of the
    :ref:`Managed resources <managed_resource_definition>`
    (e.g., the data stored in the Nova database)
-   the data stored in the
    :ref:`Cluster History Database <cluster_history_db_definition>`
    which provides information about the past of the
    :ref:`Cluster <cluster_definition>`

So far, only one :ref:`Strategy <strategy_definition>` can be associated to a
given :ref:`Goal <goal_definition>` via the main Watcher configuration file.

.. _data_model:

Data model
==========

The following diagram shows the data model of Watcher, especially the
functional dependency of objects from the actors (Admin, Customer) point of
view (Goals, Audits, Action Plans, ...):

.. image:: ./images/functional_data_model.svg
   :width: 100%

.. _sequence_diagrams:

Sequence diagrams
=================

The following paragraph shows the messages exchanged between the different
components of Watcher for the most often used scenarios.

.. _sequence_diagrams_create_audit_template:

Create a new Audit Template
---------------------------

The :ref:`Administrator <administrator_definition>` first creates an
:ref:`Audit template <audit_template_definition>` providing at least the
following parameters:

-   A name
-   A goal to achieve

.. image:: ./images/sequence_create_audit_template.png
   :width: 100%

The `Watcher API`_  just makes sure that the goal exists (i.e. it is declared
in the Watcher configuration file) and stores a new audit template in the
:ref:`Watcher Database <watcher_database_definition>`.

.. _sequence_diagrams_create_and_launch_audit:

Create and launch a new Audit
-----------------------------

The :ref:`Administrator <administrator_definition>` can then launch a new
:ref:`Audit <audit_definition>` by providing at least the unique UUID of the
previously created :ref:`Audit template <audit_template_definition>`:

.. image:: ./images/sequence_create_and_launch_audit.png
   :width: 100%

A message is sent on the :ref:`AMQP bus <amqp_bus_definition>` which triggers
the Audit in the
:ref:`Watcher Decision Engine <watcher_decision_engine_definition>`:

.. image:: ./images/sequence_trigger_audit_in_decision_engine.png
   :width: 100%

The :ref:`Watcher Decision Engine <watcher_decision_engine_definition>` reads
the Audit parameters from the
:ref:`Watcher Database <watcher_database_definition>`. It instantiates the
appropriate :ref:`Strategy <strategy_definition>` (using entry points)
associated to the :ref:`Goal <goal_definition>` of the
:ref:`Audit <audit_definition>` (it uses the information of the Watcher
configuration file to find the mapping between the
:ref:`Goal <goal_definition>` and the :ref:`Strategy <strategy_definition>`
python class).

The :ref:`Watcher Decision Engine <watcher_decision_engine_definition>` also
builds the :ref:`Cluster Data Model <cluster_data_model_definition>`. This
data model is needed by the :ref:`Strategy <strategy_definition>` to know the
current state and topology of the audited
:ref:`Openstack cluster <cluster_definition>`.

The :ref:`Watcher Decision Engine <watcher_decision_engine_definition>` calls
the **execute()** method of the instantiated
:ref:`Strategy <strategy_definition>` and provides the data model as an input
parameter. This method computes a :ref:`Solution <strategy_definition>` to
achieve the goal and returns it to the
:ref:`Decision Engine <watcher_decision_engine_definition>`. At this point,
actions are not scheduled yet.

The :ref:`Watcher Decision Engine <watcher_decision_engine_definition>`
dynamically loads the :ref:`Watcher Planner <watcher_planner_definition>`
implementation which is configured in Watcher (via entry points) and calls the
**schedule()** method of this class with the solution as an input parameter.
This method finds an appropriate scheduling of
:ref:`Actions <action_definition>` taking into account some scheduling rules
(such as priorities between actions).
It generates a new :ref:`Action Plan <action_plan_definition>` with status
**RECOMMENDED** and saves it into the
:ref:`Watcher Database <watcher_database_definition>`. The saved action plan is
now a scheduled flow of actions.

If every step executed successfully, the
:ref:`Watcher Decision Engine <watcher_decision_engine_definition>` updates
the current status of the Audit to **SUCCEEDED** in the
:ref:`Watcher Database <watcher_database_definition>` and sends a notification
on the bus to inform other components that the :ref:`Audit <audit_definition>`
was successful.


.. _sequence_diagrams_launch_action_plan:

Launch Action Plan
------------------

The :ref:`Administrator <administrator_definition>` can then launch the
recommended :ref:`Action Plan <action_plan_definition>`:

.. image:: ./images/sequence_launch_action_plan.png
   :width: 100%

A message is sent on the :ref:`AMQP bus <amqp_bus_definition>` which triggers
the :ref:`Action Plan <action_plan_definition>` in the
:ref:`Watcher Applier <watcher_applier_definition>`:

.. image:: ./images/sequence_launch_action_plan_in_applier.png
   :width: 100%

The :ref:`Watcher Applier <watcher_applier_definition>` will get the
description of the flow of :ref:`Actions <action_definition>` from the
:ref:`Watcher Database <watcher_database_definition>` and for each
:ref:`Action <action_definition>` it will instantiate a corresponding
:ref:`Action <action_definition>` handler python class.

The :ref:`Watcher Applier <watcher_applier_definition>` will then call the
following methods of the :ref:`Action <action_definition>` handler:

-   **validate_parameters()**: this method will make sure that all the
    provided input parameters are valid:

    -   If all parameters are valid, the Watcher Applier moves on to the next
        step.
    -   If it is not, an error is raised and the action is not executed. A
        notification is sent on the bus informing other components of the
        failure.

-   **preconditions()**: this method will make sure that all conditions are met
    before executing the action (for example, it makes sure that an instance
    still exists before trying to migrate it).
-   **execute()**: this method is what triggers real commands on other
    OpenStack services (such as Nova, ...) in order to change target resource
    state. If the action is successfully executed, a notification message is
    sent on the bus indicating that the new state of the action is
    **SUCCEEDED**.

If every action of the action flow has been executed successfully, a
notification is sent on the bus to indicate that the whole
:ref:`Action Plan <action_plan_definition>` has **SUCCEEDED**.


.. _state_machine_diagrams:

State Machine diagrams
======================

.. _audit_state_machine:

Audit State Machine
-------------------

The following diagram shows the different possible states of an
:ref:`Audit <audit_definition>` and what event makes the state change to a new
value:

.. image:: ./images/audit_state_machine.png
   :width: 100%

.. _action_plan_state_machine:

Action Plan State Machine
-------------------------

The following diagram shows the different possible states of an
:ref:`Action Plan <action_plan_definition>` and what event makes the state
change to a new value:

.. image:: ./images/action_plan_state_machine.png
   :width: 100%



.. _Watcher API: webapi/v1.html

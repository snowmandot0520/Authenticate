from __future__ import unicode_literals
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.contrib import messages
from notifications import notify
from groupmanagement.models import GroupDescription
from groupmanagement.models import GroupRequest
from groupmanagement.models import HiddenGroup
from groupmanagement.models import OpenGroup
from authentication.models import AuthServicesInfo
from eveonline.managers import EveManager
from django.utils.translation import ugettext_lazy as _
from django.db.models import Count
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404
from itertools import chain

import logging

logger = logging.getLogger(__name__)


@login_required
@permission_required('auth.group_management')
def group_management(request):
    logger.debug("group_management called by user %s" % request.user)
    acceptrequests = []
    leaverequests = []

    for grouprequest in GroupRequest.objects.all():
        if grouprequest.leave_request:
            leaverequests.append(grouprequest)
        else:
            acceptrequests.append(grouprequest)
    logger.debug("Providing user %s with %s acceptrequests and %s leaverequests." % (
        request.user, len(acceptrequests), len(leaverequests)))

    render_items = {'acceptrequests': acceptrequests, 'leaverequests': leaverequests}

    return render(request, 'registered/groupmanagement.html', context=render_items)


@login_required
@permission_required('auth.group_management')
def group_membership(request):
    logger.debug("group_membership called by user %s" % request.user)
    # Get all open and closed groups
    groups = [group for group in Group.objects.all().annotate(num_members=Count('user')).order_by('name')
              if joinable_group(group)]

    render_items = {'groups': groups}

    return render(request, 'registered/groupmembership.html', context=render_items)


@login_required
@permission_required('auth.group_management')
def group_membership_list(request, group_id):
    logger.debug("group_membership_list called by user %s for group id %s" % (request.user, group_id))
    try:
        group = Group.objects.get(id=group_id)

        # Check its a joinable group i.e. not corp or internal
        if not joinable_group(group):
            raise PermissionDenied

    except ObjectDoesNotExist:
        raise Http404("Group does not exist")

    members = list()

    for member in group.user_set.all():
        authinfo = AuthServicesInfo.objects.get_or_create(user=member)[0]

        members.append({
            'user': member,
            'main_char': EveManager.get_character_by_id(authinfo.main_char_id)
        })

    render_items = {'group': group, 'members': members}

    return render(request, 'registered/groupmembers.html', context=render_items)


@login_required
@permission_required('auth.group_management')
def group_membership_remove(request, group_id, user_id):
    logger.debug("group_membership_remove called by user %s for group id %s on user id %s" %
                 (request.user, group_id, user_id))
    try:
        group = Group.objects.get(id=group_id)

        try:
            user = group.user_set.get(id=user_id)
            # Remove group from user
            user.groups.remove(group)
            messages.success(request, "Removed user %s from group %s" % (user, group))
        except ObjectDoesNotExist:
            messages.warning(request, "User does not exist in that group")

    except ObjectDoesNotExist:
        messages.warning(request, "Group does not exist")

    return redirect('auth_group_membership_list', group_id)


@login_required
@permission_required('auth.group_management')
def group_accept_request(request, group_request_id):
    logger.debug("group_accept_request called by user %s for grouprequest id %s" % (request.user, group_request_id))
    try:
        group_request = GroupRequest.objects.get(id=group_request_id)
        group, created = Group.objects.get_or_create(name=group_request.group.name)
        group_request.user.groups.add(group)
        group_request.user.save()
        group_request.delete()
        logger.info("User %s accepted group request from user %s to group %s" % (
            request.user, group_request.user, group_request.group.name))
        notify(group_request.user, "Group Application Accepted", level="success",
               message="Your application to %s has been accepted." % group_request.group)
        messages.success(request,
                         'Accepted application from %s to %s.' % (group_request.main_char, group_request.group))
    except:
        messages.error(request, 'An unhandled error occurred while processing the application from %s to %s.' % (
            group_request.main_char, group_request.group))
        logger.exception("Unhandled exception occurred while user %s attempting to accept grouprequest id %s." % (
            request.user, group_request_id))
        pass

    return redirect("auth_group_management")


@login_required
@permission_required('auth.group_management')
def group_reject_request(request, group_request_id):
    logger.debug("group_reject_request called by user %s for group request id %s" % (request.user, group_request_id))
    try:
        group_request = GroupRequest.objects.get(id=group_request_id)

        if group_request:
            logger.info("User %s rejected group request from user %s to group %s" % (
                request.user, group_request.user, group_request.group.name))
            group_request.delete()
            notify(group_request.user, "Group Application Rejected", level="danger",
                   message="Your application to %s has been rejected." % group_request.group)
            messages.success(request,
                             'Rejected application from %s to %s.' % (group_request.main_char, group_request.group))
    except:
        messages.error(request, 'An unhandled error occured while processing the application from %s to %s.' % (
            group_request.main_char, group_request.group))
        logger.exception("Unhandled exception occured while user %s attempting to reject group request id %s" % (
            request.user, group_request_id))
        pass

    return redirect("auth_group_management")


@login_required
@permission_required('auth.group_management')
def group_leave_accept_request(request, group_request_id):
    logger.debug(
        "group_leave_accept_request called by user %s for group request id %s" % (request.user, group_request_id))
    try:
        group_request = GroupRequest.objects.get(id=group_request_id)
        group, created = Group.objects.get_or_create(name=group_request.group.name)
        group_request.user.groups.remove(group)
        group_request.user.save()
        group_request.delete()
        logger.info("User %s accepted group leave request from user %s to group %s" % (
            request.user, group_request.user, group_request.group.name))
        notify(group_request.user, "Group Leave Request Accepted", level="success",
               message="Your request to leave %s has been accepted." % group_request.group)
        messages.success(request,
                         'Accepted application from %s to leave %s.' % (group_request.main_char, group_request.group))
    except:
        messages.error(request, 'An unhandled error occured while processing the application from %s to leave %s.' % (
            group_request.main_char, group_request.group))
        logger.exception("Unhandled exception occured while user %s attempting to accept group leave request id %s" % (
            request.user, group_request_id))
        pass

    return redirect("auth_group_management")


@login_required
@permission_required('auth.group_management')
def group_leave_reject_request(request, group_request_id):
    logger.debug(
        "group_leave_reject_request called by user %s for group request id %s" % (request.user, group_request_id))
    try:
        group_request = GroupRequest.objects.get(id=group_request_id)

        if group_request:
            group_request.delete()
            logger.info("User %s rejected group leave request from user %s for group %s" % (
                request.user, group_request.user, group_request.group.name))
            notify(group_request.user, "Group Leave Request Rejected", level="danger",
                   message="Your request to leave %s has been rejected." % group_request.group)
            messages.success(request, 'Rejected application from %s to leave %s.' % (
                group_request.main_char, group_request.group))
    except:
        messages.error(request, 'An unhandled error occured while processing the application from %s to leave %s.' % (
            group_request.main_char, group_request.group))
        logger.exception("Unhandled exception occured while user %s attempting to reject group leave request id %s" % (
            request.user, group_request_id))
        pass

    return redirect("auth_group_management")


@login_required
def groups_view(request):
    logger.debug("groups_view called by user %s" % request.user)
    paired_list = []

    for group in Group.objects.all():
        # Check if group is a corp
        if not joinable_group(group):
            pass
        elif HiddenGroup.objects.filter(group=group).exists():
            pass
        else:
            # Get the descriptionn
            group_desc = GroupDescription.objects.filter(group=group)
            group_request = GroupRequest.objects.filter(user=request.user).filter(group=group)

            if group_desc:
                if group_request:
                    paired_list.append((group, group_desc[0], group_request[0]))
                else:
                    paired_list.append((group, group_desc[0], ""))
            else:
                if group_request:
                    paired_list.append((group, "", group_request[0]))
                else:
                    paired_list.append((group, "", ""))

    render_items = {'pairs': paired_list}
    return render(request, 'registered/groups.html', context=render_items)


@login_required
def group_request_add(request, group_id):
    logger.debug("group_request_add called by user %s for group id %s" % (request.user, group_id))
    group = Group.objects.get(id=group_id)
    if not joinable_group(group):
        logger.warning("User %s attempted to join group id %s but it is not a joinable group" %
                       (request.user, group_id))
        messages.warning(request, "You cannot join that group")
        return redirect('auth_groups')
    if OpenGroup.objects.filter(group=group).exists():
        logger.info("%s joining %s as is an open group" % (request.user, group))
        request.user.groups.add(group)
        return redirect("auth_groups")
    auth_info = AuthServicesInfo.objects.get_or_create(user=request.user)[0]
    grouprequest = GroupRequest()
    grouprequest.status = _('Pending')
    grouprequest.group = group
    grouprequest.user = request.user
    grouprequest.main_char = EveManager.get_character_by_id(auth_info.main_char_id)
    grouprequest.leave_request = False
    grouprequest.save()
    logger.info("Created group request for user %s to group %s" % (request.user, Group.objects.get(id=group_id)))
    messages.success(request, 'Applied to group %s.' % group)
    return redirect("auth_groups")


@login_required
def group_request_leave(request, group_id):
    logger.debug("group_request_leave called by user %s for group id %s" % (request.user, group_id))
    group = Group.objects.get(id=group_id)
    if not joinable_group(group):
        logger.warning("User %s attempted to leave group id %s but it is not a joinable group" %
                       (request.user, group_id))
        messages.warning(request, "You cannot leave that group")
        return redirect('auth_groups')
    if group not in request.user.groups.all():
        logger.debug("User %s attempted to leave group id %s but they are not a member" %
                     (request.user, group_id))
        messages.warning(request, "You are not a member of that group")
        return redirect('auth_groups')
    if OpenGroup.objects.filter(group=group).exists():
        logger.info("%s leaving %s as is an open group" % (request.user, group))
        request.user.groups.remove(group)
        return redirect("auth_groups")
    auth_info = AuthServicesInfo.objects.get_or_create(user=request.user)[0]
    grouprequest = GroupRequest()
    grouprequest.status = _('Pending')
    grouprequest.group = group
    grouprequest.user = request.user
    grouprequest.main_char = EveManager.get_character_by_id(auth_info.main_char_id)
    grouprequest.leave_request = True
    grouprequest.save()
    logger.info("Created group leave request for user %s to group %s" % (request.user, Group.objects.get(id=group_id)))
    messages.success(request, 'Applied to leave group %s.' % group)
    return redirect("auth_groups")


def joinable_group(group):
    """
    Check if a group is a user joinable group, i.e.
    not an internal group for Corp, Alliance, Members etc
    :param group: django.contrib.auth.models.Group object
    :return: bool True if its joinable, False otherwise
    """
    return (
        "Corp_" not in group.name and
        "Alliance_" not in group.name and
        settings.DEFAULT_AUTH_GROUP not in group.name and
        settings.DEFAULT_BLUE_GROUP not in group.name
    )

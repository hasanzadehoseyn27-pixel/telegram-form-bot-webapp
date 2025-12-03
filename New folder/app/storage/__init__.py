"""
میان‌بری برای واردات یک‌خطی در دیگر بخش‌ها؛
همهٔ توابع قدیمی همان نام خود را حفظ کرده‌اند.
"""

from .counter import next_daily_number

from .admins import (
    bootstrap_admins,
    list_admins,
    add_admin,
    remove_admin,
    is_admin,
    is_owner,
    get_owner_id,
)

from .destinations import (
    bootstrap_destinations,
    add_destination,
    list_destinations,
    get_active_destination,
    get_active_id_and_title,
)

from .allowed_channels import (
    bootstrap_allowed_channels,
    list_allowed_channels,
    is_channel_allowed,
    add_allowed_channel,
    remove_allowed_channel,
)

from .required_channels import (
    bootstrap_required_channels,
    list_required_channels,
    get_required_channel_ids,
    add_required_channel,
    remove_required_channel,
)

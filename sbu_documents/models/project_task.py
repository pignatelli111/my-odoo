# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sbu_m365_deeplink = fields.Char(
        string='M365 deep link',
        tracking=True,
        help='Optional link to the same work item in Planner, Teams, or Outlook. '
        'Prefer keeping execution in Microsoft 365; Odoo remains the job record.',
    )

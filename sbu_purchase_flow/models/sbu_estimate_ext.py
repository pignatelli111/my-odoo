# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


class SbuEstimate(models.Model):
    _inherit = 'sbu.estimate'

    def action_create_workflow_purchase_requests(self):
        """Create one purchase request per workflow route (from cost family on ANACO lines)."""
        self.ensure_one()
        if self.state != 'won':
            raise UserError(
                _('Purchase requests by workflow require the estimate in «Won» state.')
            )
        if not self.project_id:
            raise UserError(
                _('Create the project (job) from this estimate first.')
            )
        return self.project_id.action_sbu_create_purchase_requests_by_workflow()

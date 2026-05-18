# -*- coding: utf-8 -*-
from odoo import models


class SbuEstimate(models.Model):
    _inherit = 'sbu.estimate'

    def action_refresh_sal_finance_links(self):
        self.mapped('sal_line_ids').action_refresh_sal_finance_links()
        return True

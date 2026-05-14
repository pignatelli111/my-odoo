# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError


class SbuMailIngestRoute(models.Model):
    """Inbound alias that forwards mail (and attachments) to an RFQ/PO.

    Use when a vendor should email one stable address for a job or account,
    instead of the per-RFQ address on ``purchase.order``.
    """
    _name = 'sbu.mail.ingest.route'
    _description = 'SBU mail ingest route (supplier → RFQ/PO)'
    _inherit = ['mail.thread', 'mail.alias.mixin.optional']
    _order = 'name'

    name = fields.Char(string='Label', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        domain="[('supplier_rank', '>', 0)]",
        index=True,
        help='Supplier messages are matched to purchase orders for this vendor.',
    )
    project_id = fields.Many2one(
        'project.project',
        string='Job / project filter',
        index=True,
        help='If set, only RFQ/PO linked to this project are considered.',
    )
    routing = fields.Selection(
        selection=[
            ('latest_draft_rfq', 'Latest draft RFQ'),
            ('latest_sent_rfq', 'Latest RFQ sent'),
            ('latest_po', 'Latest confirmed PO'),
            ('fixed_po', 'Fixed RFQ/PO'),
        ],
        string='Attach to',
        default='latest_draft_rfq',
        required=True,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Target RFQ/PO',
        domain="[('partner_id', '=', partner_id)]",
        help='Used when «Attach to» is «Fixed RFQ/PO».',
    )

    def _alias_get_creation_values(self):
        vals = super()._alias_get_creation_values()
        vals['alias_model_id'] = self.env['ir.model']._get_id(self._name)
        vals['alias_defaults'] = '{}'
        if self.id:
            vals['alias_force_thread_id'] = self.id
        vals['alias_contact'] = 'everyone'
        return vals

    def _sbu_domain_for_purchase_orders(self):
        self.ensure_one()
        dom = [
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id),
        ]
        if self.project_id:
            dom.append(('project_id', '=', self.project_id.id))
        return dom

    def _resolve_target_purchase_order(self):
        self.ensure_one()
        PO = self.env['purchase.order'].sudo()
        if self.routing == 'fixed_po':
            po = self.purchase_order_id
            if not po or po.partner_id != self.partner_id:
                return self.env['purchase.order']
            if self.project_id and po.project_id and po.project_id != self.project_id:
                return self.env['purchase.order']
            return po

        dom = self._sbu_domain_for_purchase_orders()
        order = 'date_order desc, id desc'
        if self.routing == 'latest_draft_rfq':
            dom.append(('state', '=', 'draft'))
        elif self.routing == 'latest_sent_rfq':
            dom.append(('state', '=', 'sent'))
        elif self.routing == 'latest_po':
            dom.append(('state', '=', 'purchase'))
        else:
            return self.env['purchase.order']
        return PO.search(dom, order=order, limit=1)

    def _message_post_after_hook(self, message, msg_values):
        res = super()._message_post_after_hook(message, msg_values)
        if self.env.context.get('sbu_mail_ingest_skip_forward'):
            return res
        for route in self:
            target = route._resolve_target_purchase_order()
            if not target:
                route.with_context(sbu_mail_ingest_skip_forward=True).message_post(
                    body=Markup('<p><em>%s</em></p>')
                    % _('No matching RFQ/PO was found; nothing was forwarded. Check routing rules and project filter.'),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
                continue
            att_ids = message.attachment_ids.ids
            intro = Markup('<p><em>%s</em></p>') % _(
                'Forwarded from mail ingest «%s» → %s'
            ) % (route.display_name, target.display_name)
            body = intro
            if message.body:
                body += Markup(message.body)
            target.with_context(sbu_mail_ingest_forwarding=True).message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
                attachment_ids=[(6, 0, att_ids)] if att_ids else [],
                partner_ids=[(6, 0, message.partner_ids.ids)] if message.partner_ids else [],
            )
        return res

    @api.constrains('routing', 'purchase_order_id', 'partner_id')
    def _check_fixed_po(self):
        for route in self:
            if route.routing != 'fixed_po':
                continue
            if not route.purchase_order_id:
                raise UserError(_('Fixed RFQ/PO routing requires a target purchase order.'))
            if route.purchase_order_id.partner_id != route.partner_id:
                raise UserError(_('Target purchase order must be for the same vendor.'))

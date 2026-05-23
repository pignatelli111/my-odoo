# -*- coding: utf-8 -*-
from odoo.addons.sbu_closure.hooks import _sync_closure_document_type_translations


def migrate(cr, version):
  if not version:
      return
  from odoo import api, SUPERUSER_ID
  env = api.Environment(cr, SUPERUSER_ID, {})
  _sync_closure_document_type_translations(env)

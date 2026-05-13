# Odoo 19 removed the model uom.category; UoM is now a tree via uom.uom.relative_uom_id.
# Custom SBU units (mm, mq, rot, …) must be created with that API or configured manually.
# Intentionally no post_init_hook — avoids KeyError and keeps install reliable.

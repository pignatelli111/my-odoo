{
    "name": "SBU Integrations",
    "version": "19.0.1.4.0",
    "summary": "Microsoft Graph, OneDrive naming, Teams/Planner collaboration policy (Phase 5.1–5.3)",
    "author": "SBU Development",
    "category": "Technical",
    "depends": ["base", "base_setup", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/sbu_icp_sync_wizard_views.xml",
        "views/sbu_app_review_wizard_views.xml",
        "views/sbu_bank_statement_import_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}

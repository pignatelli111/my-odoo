{
    "name": "SBU Documents",
    "version": "19.0.1.0.7",
    "summary": "M365 docs + Graph sync + Teams/Planner/Outlook deep links (Phase 5.1–5.3)",
    "author": "SBU Development",
    "category": "Document Management",
    "depends": [
        "base",
        "project",
        "sbu_estimate",
        "sbu_integrations",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/sbu_documents_rules.xml",
        "views/project_document_hub.xml",
        "views/project_m365_collaboration_views.xml",
        "views/project_task_m365_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}

{
    'name': 'SBU Purchase Flow',
    'version': '19.0.1.0.0',
    'summary': 'RDA/ACO/ACP/LDS purchase request flow for Suburban SRL',
    'description': '''
        Translates the internal order documents into Odoo:
        - RDA: Richiesta Acquisto Materiali Primari
        - ACP: Accessori Posa
        - ACO: Accessori Officina
        - LDS: Lista di Spedizione
        - FE, ST, LZ, VT, PAN, LA, PRF, ASS, SE
        - Supplier comparison matrix
        - Full traceability: estimate → request → RFQ → PO → delivery
    ''',
    'author': 'SBU Development',
    'category': 'Purchase',
    'depends': [
        'base',
        'purchase',
        'stock',
        'sbu_estimate',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sbu_purchase_sequence.xml',
        'views/sbu_purchase_request_views.xml',
        'views/sbu_purchase_request_line_views.xml',
        'views/sbu_supplier_comparison_views.xml',
        'views/sbu_purchase_menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

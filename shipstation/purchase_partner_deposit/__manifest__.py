{
    'name': 'Novobi: Purchase Partner Deposit',
    'summary': 'Novobi: Purchase Partner Deposit',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '15.1.0',
    'depends': [
        'account_partner_deposit',
        'purchase'
    ],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================

        # ============================== VIEWS ================================
        'views/account_payment_deposit_view.xml',
        'views/purchase_order_view.xml',

        # ============================== REPORT ===============================

        # ============================== WIZARDS ==============================
    ],
    'installable': True,
    'auto_install': False,
    'license': 'OPL-1'
}

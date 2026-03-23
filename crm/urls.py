from django.urls import path
from .views import *

urlpatterns = [
    #navigation
    path("navigation/", NavigationView.as_view()),

    #users
    path("users/", UserListView.as_view(), name="users-list"),

    #schema
            path("debug/", debug_schema),

    path("schema/leads/", SchemaView.as_view(), name="leads-schema"),
    path("schema/customers/", CustomerSchemaView.as_view()),
    path("schema/expenses/", ExpenseSchemaView.as_view()),
    path("schema/inventories/", InventorySchemaView.as_view()),
    path("schema/vendors/", VendorSchemaView.as_view()),
    path("schema/invoices/", InvoiceSchemaView.as_view()),
    path("schema/manual-journals/", ManualJournalSchemaView.as_view()),
    path("schema/expense-invoices/", ExpenseInvoiceSchemaView.as_view()),
    path("schema/company-profile/", CompanyProfileSchemaView.as_view()),
    path("inventory-sales-invoices/schema/",InventorySalesInvoiceSchemaView.as_view()),
    path("inventory-invoices/schema/",InventoryInvoiceSchemaView.as_view()),

    
    #Dashboard
    path("dashboard/", DashboardView.as_view()),


    #leads
    path("leads/", LeadCreateView.as_view()), 
    path("leads/list/", LeadListView.as_view()), 
    path("leads/<int:pk>/", LeadDetailView.as_view(), name="lead-detail"), 
    path("leads/<int:pk>/update/", LeadUpdateView.as_view()),
    path("leads/<int:pk>/delete/", LeadDeleteView.as_view()),
    path("leads/<int:pk>/notes/add/", LeadAddNoteView.as_view()),
    path("leads/<int:pk>/notes/<int:note_id>/delete/", LeadDeleteNoteView.as_view()),


    #customers
    path("customers/list/", CustomerListView.as_view()),
    path("customers/", CustomerCreateView.as_view()),
    path("customers/<int:pk>/", CustomerDetailView.as_view()),
    path("customers/<int:pk>/update/", CustomerUpdateView.as_view()),
    path("customers/<int:pk>/notes/add/", CustomerAddNoteView.as_view()),
    path("customers/<int:pk>/notes/<str:note_id>/delete/", CustomerDeleteNoteView.as_view()),
    path("customers/<int:pk>/delete/", CustomerDeleteView.as_view()),

    #chartofaccounts
    path("accounts/list/", AccountListView.as_view()),
    path("accounts/", AccountCreateView.as_view()),
    path("accounts/<int:pk>/delete/", AccountDeleteView.as_view()),
    path("accounts/<int:pk>/update/", AccountUpdateView.as_view()),
    path("accounts/by-type/", AccountListByTypeView.as_view()),


    #expenses
    path("expenses/list/", ExpenseListView.as_view()),
    path("expenses/", ExpenseCreateView.as_view()),
    path("expenses/<int:pk>/", ExpenseDetailView.as_view()),
    path("expenses/<int:pk>/update/", ExpenseUpdateView.as_view()),
    path("expense-invoices/import/", ExpenseInvoiceImportView.as_view()),
    path("expenses/<int:pk>/delete/", ExpenseDeleteView.as_view()),

    path("expenses/<int:pk>/post/", ExpensePostView.as_view()),



    # Inventory 
    path("inventories/list/", InventoryListView.as_view()),
    path("inventories/", InventoryCreateView.as_view()),
    path("inventories/<int:pk>/", InventoryDetailView.as_view()),
    path("inventories/<int:pk>/update/", InventoryUpdateView.as_view()),
    path("inventories/<int:pk>/delete/", InventoryDeleteView.as_view()),

   

   # vendors
   path("vendors/list/", VendorListView.as_view()),
   path("vendors/", VendorCreateView.as_view()),
   path("vendors/<int:pk>/", VendorDetailView.as_view()),
   path("vendors/<int:pk>/update/", VendorUpdateView.as_view()),
   path("vendors/<int:pk>/notes/add/", VendorAddNoteView.as_view()),
   path("vendors/<int:pk>/notes/<str:note_id>/delete/", VendorDeleteNoteView.as_view()),
   path("vendors/<int:pk>/delete/", VendorDeleteView.as_view()),


    # Invoice 
    path("invoices/", InvoiceCreateView.as_view()),
    path("invoices/list/", InvoiceListView.as_view()),
    path("invoices/<int:pk>/", InvoiceDetailView.as_view()),
    path("invoices/<int:pk>/update/", InvoiceUpdateView.as_view()),
    path("invoices/<int:pk>/pdf/", InvoicePDFView.as_view()),
    path("invoices/<int:pk>/delete/", InvoiceDeleteView.as_view()),
    path("invoices/<int:pk>/notes/add/", InvoiceAddNoteView.as_view()),
    path("invoices/<int:pk>/notes/<str:note_id>/delete/", InvoiceDeleteNoteView.as_view()),
    path("invoices/<int:pk>/post/", InvoicePostView.as_view()),
    path("invoices/<int:pk>/mark-paid/", InvoiceMarkPaidView.as_view()),


    # Invoice Adjustments
    path("invoices/originals/", OriginalInvoiceListView.as_view()),
    path("invoices/adjustment/", InvoiceAdjustmentCreateView.as_view()),
    path("invoices/adjustments/list/", InvoiceAdjustmentListPageView.as_view()),
    path("invoice-adjustments/<int:adjustment_id>/", InvoiceAdjustmentDetailView.as_view()),
    path("invoice-adjustments/<int:adjustment_id>/mark-paid/",InvoiceAdjustmentMarkPaidView.as_view()),

    # Manual Journal
    path("manual-journals/", ManualJournalCreateView.as_view()),
    path("manual-journals/list/", ManualJournalListView.as_view()),
    path("manual-journals/<int:pk>/", ManualJournalDetailView.as_view()),
    path("manual-journals/<int:pk>/delete/", ManualJournalDeleteView.as_view()),
    path("manual-journals/<int:pk>/update/", ManualJournalUpdateView.as_view()),


    # Expenses Invoice 
    path("expense-invoices/", ExpenseInvoiceCreateView.as_view()),
    path("expense-invoices/list/", ExpenseInvoiceListView.as_view()),
    path("expense-invoices/<int:pk>/", ExpenseInvoiceDetailView.as_view()),
    path("expense-invoices/<int:pk>/update/", ExpenseInvoiceUpdateView.as_view()),
    path("expense-invoices/<int:pk>/delete/", ExpenseInvoiceDeleteView.as_view()),
    path("expense-invoices/<int:pk>/mark-paid/", ExpenseInvoiceMarkPaidView.as_view()),




    # Company Profile
    path("company-profile/", CompanyProfileDetailView.as_view()),
    path("company-profile/save/", CompanyProfileSaveView.as_view()),
    path("company-profile/delete/", CompanyProfileDeleteView.as_view()),



    # INVENTORY PURCHASE INVOICES
    path("inventory-invoices/",InventoryInvoiceListView.as_view()),
    path("inventory-invoices/create/",InventoryInvoiceCreateView.as_view()),
    path("inventory-invoices/<int:pk>/",InventoryInvoiceDetailView.as_view()),
    path("inventory-invoices/<int:pk>/pdf/",InventoryInvoicePDFView.as_view()),
    path("invoice-adjustments/<int:pk>/pdf/",InvoiceAdjustmentPDFView.as_view()),
    path("inventory-invoices/<int:pk>/post/", InventoryInvoicePostView.as_view()),
    path("inventory-invoices/<int:pk>/mark-paid/", InventoryInvoiceMarkPaidView.as_view()),


    # INVENTORY SALES INVOICES
    path("inventory-sales-invoices/",InventorySalesInvoiceListView.as_view()),
    path("inventory-sales-invoices/<int:pk>/",InventorySalesInvoiceDetailView.as_view()),
    path("inventory-sales-invoices/create/",InventorySalesInvoiceCreateView.as_view()),
    path("inventory-sales-invoices/<int:pk>/post/",InventorySalesInvoicePostView.as_view()),
    path("inventory-sales-invoices/<int:pk>/mark-paid/",InventorySalesInvoiceMarkPaidView.as_view()),
    path("inventory-sales-invoices/<int:pk>/pdf/",InventorySalesInvoicePDFView.as_view()),


    #reports
    path("reports/profit-loss/", ProfitLossReportView.as_view()),
    path("reports/balance-sheet/", BalanceSheetView.as_view()),
    path("reports/statement-of-account/", StatementOfAccountView.as_view()),
    path("reports/vendor-statement/", VendorStatementView.as_view()),
    path("reports/cash-flow/", CashFlowReportView.as_view()),



    #tasks
    path("tasks/", TaskListView.as_view()),
    path("tasks/create/", TaskCreateView.as_view()),
    path("tasks/<int:pk>/update/", TaskUpdateView.as_view()),
    path("tasks/<int:pk>/delete/", TaskDeleteView.as_view()),
    path("tasks/<int:pk>/", TaskDetailView.as_view()),
    path("tasks/<int:pk>/mark-done/", TaskMarkAsDoneView.as_view()),

    #notifications
    path("notifications/", NotificationsView.as_view()),
    path("notifications/inventory/", InventoryNotificationsView.as_view()),

    #migrations
    path("customers/import/", CustomerCSVImportView.as_view()),
    path("leads/import/", LeadCSVImportView.as_view()),


    #Payroll
    path("payroll/company-wps/", CompanyWPSCreateView.as_view()),
    path("payroll/employees/create/", EmployeeCreateView.as_view()),
    path("payroll/employees/", EmployeeListView.as_view()),
    path("payroll/run/", PayrollRunView.as_view()),
    path("payroll/generate-sif/", GenerateSIFView.as_view()),
    path("payroll/employees/<int:id>/delete/",EmployeeDeleteView.as_view()),


    #bank recon
    path("bank/accounts/create/", BankAccountCreateView.as_view()),
    path("bank/accounts/", BankAccountListView.as_view()),    
    path("bank/upload-statement/", UploadBankStatementView.as_view()),
    path("bank/transactions/", BankStatementTransactionsView.as_view()),
    path("bank/reconcile/", RunBankReconciliationView.as_view()),
    path("bank/reconciliation-summary/", BankReconciliationSummaryView.as_view()),
    


    

]
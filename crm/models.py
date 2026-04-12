from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal ,ROUND_HALF_UP

from django.utils import timezone
import uuid

User = get_user_model()


class Lead(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    company = models.CharField(max_length=200, blank=True, null=True)

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_leads"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_leads"
    )

    extra_data = models.JSONField(default=dict, blank=True)
    notes = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.name
    



class Customer(models.Model):
    # Core Identity
    company = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    # Universal CRM Field
    status = models.CharField(max_length=50, blank=True, null=True)

    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_customers"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customers"
    )

    # Dynamic Fields
    extra_data = models.JSONField(default=dict, blank=True)

    # Notes / Activities
    notes = models.JSONField(default=list, blank=True)

    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.company
    


# models.py
from django.conf import settings
class Account(models.Model):
    ACCOUNT_TYPES = [
        ("Asset", "Asset"),
        ("Liability", "Liability"),
        ("Equity", "Equity"),
        ("Revenue", "Revenue"),
        ("Expense", "Expense"),
    ]

    accountid = models.CharField(max_length=50, unique=True, null=True, blank=True) 

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)

    description = models.TextField(blank=True, null=True)
    vat_applicable = models.BooleanField(default=False)

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"
    




class Expense(models.Model):

    # Identity
    expense_number = models.CharField(max_length=50, unique=True)

    # Basic Info
    date = models.DateField()

    # 🔥 PROFESSIONAL LINK
    vendor = models.ForeignKey(
        "Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses"
    )

    currency = models.CharField(max_length=10, default="AED")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    vat_applicable = models.BooleanField(default=True)

    # 🔥 No manual vat_amount storage (optional but cleaner)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Classification
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True
    )

    payment_account = models.ForeignKey(
    Account,
    on_delete=models.PROTECT,
    related_name="paid_expenses",
    null=True,
    blank=True
)
    status = models.CharField(max_length=20, default="DRAFT")

    notes = models.TextField(blank=True, null=True)

    extra_data = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_expenses"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["expense_number"]),
        ]

    def save(self, *args, **kwargs):
        amount = self.amount or Decimal("0.00")

        if self.vat_applicable:
            self.vat_amount = (amount * Decimal("0.05")).quantize(Decimal("0.01"))
        else:
            self.vat_amount = Decimal("0.00")

        self.total = (amount + self.vat_amount).quantize(Decimal("0.01"))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.expense_number}"



class ExpenseAttachment(models.Model):

    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name="attachments"
    )

    file = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.file_name and self.file:
            self.file_name = self.file.name
        super().save(*args, **kwargs)

    def __str__(self):
        return self.file_name or "Attachment"



class InventoryItem(models.Model):

    # =============================
    # PRODUCT IDENTITY
    # =============================

    item_code = models.CharField(max_length=50, unique=True)
    item_name = models.CharField(max_length=200)

    # =============================
    # CLASSIFICATION
    # =============================

    category = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    unit_of_measure = models.CharField(max_length=50, default="Unit")

    # =============================
    # PRICING
    # =============================

    # Weighted average cost
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # Selling price (used in sales invoices)
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # =============================
    # STOCK STATE
    # =============================

    current_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    minimum_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    warehouse = models.CharField(max_length=100, blank=True, null=True)

    # =============================
    # SYSTEM
    # =============================

    status = models.CharField(max_length=50, default="ACTIVE")

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inventory_items"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item_code"]),
            models.Index(fields=["item_name"]),
            models.Index(fields=["category"]),
            models.Index(fields=["status"]),
        ]

    # =============================
    # DERIVED VALUE (NOT STORED)
    # =============================

    @property
    def inventory_value(self):
        return (self.current_quantity * self.cost_price).quantize(
            Decimal("0.01")
        )

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"
    

class InventoryTransaction(models.Model):

    TRANSACTION_TYPES = [
        ("PURCHASE", "Purchase"),
        ("SALE", "Sale"),
        ("ADJUSTMENT", "Adjustment"),
        ("RETURN", "Return"),
    ]

    item = models.ForeignKey(
        "InventoryItem",
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]



class Vendor(models.Model):

    # Core Identity
    company = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    # Status
    status = models.CharField(max_length=50, blank=True, null=True)

    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_vendors"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_vendors"
    )

    # Dynamic Fields
    extra_data = models.JSONField(default=dict, blank=True)

    # Notes
    notes = models.JSONField(default=list, blank=True)

    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.company



class Invoice(models.Model):

    # Customer Relation (nullable for custom invoice)
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices"
    )

    # Custom invoice details (if not existing customer)
    custom_details = models.JSONField(default=dict, blank=True)

    add_as_customer = models.BooleanField(default=False)

    # Dates
    date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=50, default="draft")

    # Invoice Number
    number = models.CharField(max_length=50, unique=True, blank=True)

    # Items
    items = models.JSONField(default=list, blank=True)

    # Totals
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Dynamic fields
    extra_data = models.JSONField(default=dict, blank=True)

    notes = models.JSONField(default=list, blank=True)

    document_type = models.CharField(
    max_length=20,
    choices=[
        ("INVOICE", "Invoice"),
        ("CREDIT_NOTE", "Credit Note"),
        ("DEBIT_NOTE", "Debit Note"),
    ],
    default="INVOICE"
)

    related_invoice = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="adjustments"
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL
    )

    

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_number(self):
        if not self.number:
            self.number = f"INV-{uuid.uuid4().hex[:8].upper()}"

    def calculate_totals(self):
        subtotal = Decimal("0.00")
        vat_total = Decimal("0.00")

        for item in self.items:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            amount = (qty * price).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
            item["amount"] = float(amount)
            subtotal += amount
            
            # Only add VAT if the item has vat_included = True
            if item.get("vat_included", False):
                vat_total += amount * Decimal("0.05")

        # Round VAT to 2 decimal places
        vat = vat_total.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        total = subtotal + vat

        self.subtotal = subtotal
        self.vat = vat
        self.total = total

    def save(self, *args, **kwargs):
        self.generate_number()
        self.calculate_totals()  # Now respects vat_included flag
        super().save(*args, **kwargs)


    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.number


from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User
import uuid

class InventoryInvoice(models.Model):

    vendor = models.ForeignKey(
        "Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_invoices"
    )

    date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=50,
        default="draft"
    )

    number = models.CharField(
        max_length=50,
        unique=True,
        blank=True
    )

    items = models.JSONField(default=list, blank=True)

    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    notes = models.JSONField(default=list, blank=True)

    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def generate_number(self):
        if not self.number:
            self.number = f"PINV-{uuid.uuid4().hex[:8].upper()}"

    def calculate_totals(self):
        subtotal = Decimal("0.00")
        total_vat = Decimal("0.00")

        for item in self.items:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            vat_applicable = item.get("vat_applicable", False)

            amount = (qty * price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            item["amount"] = float(amount)

            subtotal += amount

            if vat_applicable:
                line_vat = (amount * Decimal("0.05")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_vat += line_vat
            else:
                line_vat = Decimal("0.00")

            item["vat_amount"] = float(line_vat)

        self.subtotal = subtotal
        self.vat = total_vat
        self.total = subtotal + total_vat

    def save(self, *args, **kwargs):
        self.generate_number()
        self.calculate_totals()
        super().save(*args, **kwargs)





class ManualJournal(models.Model):

    journal_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    currency = models.CharField(max_length=10, default="USD")
    status = models.CharField(max_length=20, default="Draft")

    notes = models.TextField(blank=True, null=True)

    # 🔥 Entries stored as JSON
    entries = models.JSONField(default=list, blank=True)

    total_debits = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_credits = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    difference = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_balanced = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_number(self):
        if not self.journal_number:
            self.journal_number = f"JRN-{uuid.uuid4().hex[:8].upper()}"

    def calculate_totals(self):
        debit_total = Decimal("0.00")
        credit_total = Decimal("0.00")

        for entry in self.entries:
            debit = Decimal(str(entry.get("debit", 0)))
            credit = Decimal(str(entry.get("credit", 0)))

            debit_total += debit
            credit_total += credit

        debit_total = debit_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        credit_total = credit_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        diff = debit_total - credit_total

        self.total_debits = debit_total
        self.total_credits = credit_total
        self.difference = diff
        self.is_balanced = abs(diff) < Decimal("0.01")

    def save(self, *args, **kwargs):
        self.generate_number()
        self.calculate_totals()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return self.journal_number



class ExpenseInvoice(models.Model):
    invoice_number = models.CharField(max_length=100)
    vendor = models.ForeignKey("Vendor", on_delete=models.SET_NULL, null=True)

    vendor_name = models.CharField(max_length=255)  # snapshot
    date = models.DateField()
    due_date = models.DateField()

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(max_length=20, default="Pending")
    invoice_type = models.CharField(max_length=30, default="EXPENSE")

    items = models.JSONField(default=list, blank=True)
    journal_entries = models.JSONField(default=list, blank=True)

    pdf_file = models.CharField(max_length=255, blank=True, null=True)

    extra_data = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ["-date"]

    @property
    def total_debits(self):
        return sum(Decimal(str(e.get("debit", 0))) for e in self.journal_entries)

    @property
    def total_credits(self):
        return sum(Decimal(str(e.get("credit", 0))) for e in self.journal_entries)

    @property
    def is_balanced(self):
        return abs(self.total_debits - self.total_credits) < Decimal("0.01")
    
    

class InventorySalesInvoice(models.Model):

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True
    )

    number = models.CharField(max_length=50, unique=True, blank=True)

    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, default="draft")

    items = models.JSONField(default=list, blank=True)

    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def generate_number(self):
        if not self.number:
            self.number = f"SINV-{uuid.uuid4().hex[:8].upper()}"

    def calculate_totals(self):
        subtotal = Decimal("0.00")
        vat_total = Decimal("0.00")

        for item in self.items:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            line = qty * price
            subtotal += line

        vat_total = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))

        self.subtotal = subtotal
        self.vat = vat_total
        self.total = subtotal + vat_total

    def save(self, *args, **kwargs):
        self.generate_number()
        self.calculate_totals()
        super().save(*args, **kwargs)



class CompanyProfile(models.Model):
    company_name = models.CharField(max_length=255)

    company_logo = models.TextField(blank=True, null=True)  # base64 image

    company_address = models.TextField()
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, default="United Arab Emirates")
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    phone_number = models.CharField(max_length=50)
    email = models.EmailField()
    website = models.CharField(max_length=255, blank=True, null=True)

    is_vat_registered = models.BooleanField(default=True)
    vat_number = models.CharField(max_length=20, blank=True, null=True)
    corporate_registration_number = models.CharField(max_length=100, blank=True, null=True)

    signature_image = models.TextField(blank=True, null=True)  # base64
    company_stamp = models.TextField(blank=True, null=True)  # base64

    custom_footer_notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]




class Task(models.Model):

    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("blocked", "Blocked"),
        ("done", "Done"),
    ]

    PRIORITY_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    RECURRENCE_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
    ]

    RELATED_TYPE_CHOICES = [
        ("none", "None"),
        ("lead", "Lead"),
        ("customer", "Customer"),
        ("vendor", "Vendor"),
    ]

    # =============================
    # BASIC INFO
    # =============================

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    due_date = models.DateField()

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="medium"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="todo"
    )

    # =============================
    # ASSIGNMENT
    # =============================

    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks"
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tasks"
    )

    # =============================
    # RELATIONS
    # =============================

    related_type = models.CharField(
        max_length=20,
        choices=RELATED_TYPE_CHOICES,
        default="none"
    )

    related_lead_id = models.IntegerField(null=True, blank=True)
    related_customer_id = models.IntegerField(null=True, blank=True)
    related_vendor_id = models.IntegerField(null=True, blank=True)

    # =============================
    # RECURRING TASK
    # =============================

    recurring = models.BooleanField(default=False)

    recurrence_pattern = models.CharField(
        max_length=20,
        choices=RECURRENCE_CHOICES,
        blank=True,
        null=True
    )

    next_due_date = models.DateField(null=True, blank=True)

    # =============================
    # TAGS
    # =============================

    tags = models.JSONField(default=list, blank=True)

    # =============================
    # SYSTEM FIELDS
    # =============================

    completed_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "-created_at"]

    def save(self, *args, **kwargs):
        if self.status == "done" and not self.completed_date:
            self.completed_date = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CompanyWPSProfile(models.Model):

    employer_name = models.CharField(max_length=200)
    employer_eid = models.CharField(max_length=50)
    establishment_card_number = models.CharField(max_length=20)
    mol_number = models.CharField(max_length=20)

    bank_swift_code = models.CharField(max_length=20)
    payroll_iban = models.CharField(max_length=34)

    created_at = models.DateTimeField(auto_now_add=True)


class Employee(models.Model):

    employee_id = models.CharField(max_length=50, unique=True)

    name = models.CharField(max_length=200)

    labour_card_number = models.CharField(max_length=50)

    bank_swift_code = models.CharField(max_length=20)

    bank_account = models.CharField(max_length=34)

    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)

    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def gross_salary(self):
        return self.basic_salary + self.allowances


class EmployeeSalaryHistory(models.Model):

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    month = models.IntegerField()
    year = models.IntegerField()

    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)

    allowances = models.DecimalField(max_digits=12, decimal_places=2)

    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    days_worked = models.IntegerField(default=30)

    gross_salary = models.DecimalField(max_digits=12, decimal_places=2)

    net_salary = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)


class WPSGenerationLog(models.Model):

    month = models.IntegerField()
    year = models.IntegerField()

    file_reference = models.CharField(max_length=100)

    employee_count = models.IntegerField()

    total_salary = models.DecimalField(max_digits=14, decimal_places=2)

    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)


















class BankAccount(models.Model):

    account_name = models.CharField(max_length=200)

    bank_name = models.CharField(max_length=200)

    account_number = models.CharField(max_length=100)

    iban = models.CharField(max_length=50, blank=True, null=True)

    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_name} - {self.bank_name}"





class BankStatementTransaction(models.Model):

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE
    )

    date = models.DateField()

    description = models.TextField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    matched = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        default="unmatched"
    )

    matched_reference = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)


class BankReconciliationLog(models.Model):

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE
    )

    reconciliation_date = models.DateField()

    statement_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    ledger_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    difference = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("reconciled", "Reconciled"),
            ("pending", "Pending"),
            ("discrepancy", "Discrepancy")
        ],
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reconciliation {self.bank_account.account_name}"




class Notification(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.message
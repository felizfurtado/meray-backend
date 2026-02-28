from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class Lead(models.Model):
    """Ultra-simple Lead model"""
    
    # Core identity fields
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    company = models.CharField(max_length=200, blank=True, null=True)
    
    # Business fields
    status = models.CharField(max_length=30, default="new")
    industry = models.CharField(max_length=50, blank=True, null=True)
    source = models.CharField(max_length=50, blank=True, null=True)
    probability = models.PositiveSmallIntegerField(default=0)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    # Relationships
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
        related_name="created_leads"
    )
    
    # Dynamic data (JSON fields)
    custom_data = models.JSONField(default=dict, blank=True)
    notes = models.JSONField(default=list, blank=True)  # Array of notes
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["industry"]),
            models.Index(fields=["source"]),
        ]
    
    def __str__(self):
        return self.name
    
    def add_note(self, text, user):
        """Add a note to the notes array"""
        note = {
            "id": len(self.notes) + 1,
            "text": text,
            "user_id": user.id,
            "user_name": user.username,
            "created_at": models.DateTimeField.now().isoformat()
        }
        self.notes.append(note)
        self.save(update_fields=['notes', 'updated_at'])
        return note
    






# Add to existing models.py file
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

User = get_user_model()

class Customer(models.Model):
    """Customer model - similar to Lead structure"""
    
    # Basic Information
    customer_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    company_name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True, null=True)
    use_same_legal_name = models.BooleanField(default=True)
    
    # Contact Information
    customer_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    
    # Business Details
    INDUSTRY_CHOICES = [
        ('trading', 'Trading'),
        ('manufacturing', 'Manufacturing'),
        ('services', 'Services'),
        ('construction', 'Construction'),
        ('food_hospitality', 'Food & Hospitality'),
        ('other', 'Other'),
    ]
    industry = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, blank=True, null=True)
    
    # Tax Information
    trn = models.CharField(max_length=15, blank=True, null=True, help_text="15-digit TRN")
    VAT_TREATMENT_CHOICES = [
        ('standard_5', 'Standard Rated (5%)'),
        ('zero_0', 'Zero Rated (0%)'),
        ('exempt', 'Exempt'),
        ('reverse_charge', 'Reverse Charge'),
    ]
    vat_treatment = models.CharField(max_length=20, choices=VAT_TREATMENT_CHOICES, blank=True, null=True)
    trn_expiry = models.DateField(blank=True, null=True)
    
    # Address Information
    billing_address = models.TextField()
    shipping_address = models.TextField(blank=True, null=True)
    use_same_shipping_address = models.BooleanField(default=True)
    
    EMIRATE_CHOICES = [
        ('abu_dhabi', 'Abu Dhabi'),
        ('dubai', 'Dubai'),
        ('sharjah', 'Sharjah'),
        ('ras_al_khaima', 'Ras Al Khaima'),
        ('ajman', 'Ajman'),
        ('fujairah', 'Fujairah'),
        ('umm_al_quwain', 'Umm Al Quwain'),
        ('other', 'Other'),
    ]
    emirate = models.CharField(max_length=50, choices=EMIRATE_CHOICES)
    country = models.CharField(max_length=50, default='United Arab Emirates')
    
    # Financial Information
    payment_terms = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        help_text="Payment terms in days"
    )
    
    # Calculated Fields (cached for performance)
    ytd_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_invoices = models.PositiveIntegerField(default=0)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overdue_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dynamic data
    notes = models.JSONField(default=list, blank=True, help_text="List of notes")
    contacts = models.JSONField(default=list, blank=True, help_text="List of contact persons")
    
    # System fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_customers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['company_name']
        indexes = [
            models.Index(fields=['company_name']),
            models.Index(fields=['customer_name']),
            models.Index(fields=['industry']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.company_name} ({self.customer_name})"
    
    def save(self, *args, **kwargs):
        # Generate customer ID if not exists
        if not self.customer_id:
            prefix = 'CUST'
            year = timezone.now().strftime('%y')
            last_customer = Customer.objects.filter(
                customer_id__startswith=f"{prefix}{year}"
            ).order_by('-customer_id').first()
            
            if last_customer and last_customer.customer_id:
                try:
                    last_number = int(last_customer.customer_id[-4:])
                    new_number = str(last_number + 1).zfill(4)
                except ValueError:
                    new_number = '0001'
            else:
                new_number = '0001'
            
            self.customer_id = f"{prefix}{year}{new_number}"
        
        # Auto-fill legal name if same as company name
        if self.use_same_legal_name and not self.legal_name:
            self.legal_name = self.company_name
        
        # Auto-fill shipping address if same as billing address
        if self.use_same_shipping_address and not self.shipping_address:
            self.shipping_address = self.billing_address
        
        super().save(*args, **kwargs)
        
        # Update calculated fields after saving
        self.update_calculated_fields()


    def add_note(self, text, user):
        """Add a note to the notes array"""
        note = {
            "id": len(self.notes) + 1,
            "text": text,
            "user_id": user.id,
            "user_name": user.username,
            "created_at": timezone.now().isoformat(),
        }
        self.notes.append(note)
        self.save(update_fields=['notes', 'updated_at'])
        return note
    
    def add_contact(self, name, email, phone=None, position=None, is_primary=False):
        """Add a contact person"""
        contact = {
            "id": len(self.contacts) + 1,
            "name": name,
            "email": email,
            "phone": phone,
            "position": position,
            "is_primary": is_primary,
            "created_at": timezone.now().isoformat(),
        }
        self.contacts.append(contact)
        
        # If setting as primary, unset others
        if is_primary:
            for c in self.contacts:
                if c.get('id') != contact['id']:
                    c['is_primary'] = False
        
        self.save(update_fields=['contacts', 'updated_at'])
        return contact
    
    def update_calculated_fields(self):
        """Update calculated financial fields from related invoices"""
        from django.db.models import Sum
        from django.utils import timezone
        
        try:
            # Get current year
            current_year = timezone.now().year
            
            # Calculate YTD sales (invoices from current year with status sent/pending/overdue/paid)
            ytd_invoices = self.invoices.filter(
                date__year=current_year,
                status__in=['sent', 'pending', 'overdue', 'paid']
            )
            ytd_sales = ytd_invoices.aggregate(total=Sum('total'))['total'] or 0
            
            # Calculate outstanding invoices and amount
            outstanding_invoices = self.invoices.filter(
                status__in=['sent', 'pending', 'overdue']
            )
            outstanding_count = outstanding_invoices.count()
            outstanding_amount = outstanding_invoices.aggregate(
                total=Sum('outstanding_amount')
            )['total'] or 0
            
            # Calculate overdue amount
            overdue_invoices = self.invoices.filter(
                status='overdue',
                is_overdue=True
            )
            overdue_amount = overdue_invoices.aggregate(
                total=Sum('outstanding_amount')
            )['total'] or 0
            
            # Update the fields
            self.ytd_sales = ytd_sales
            self.outstanding_invoices = outstanding_count
            self.outstanding_amount = outstanding_amount
            self.overdue_amount = overdue_amount
            
            # Save only the calculated fields
            Customer.objects.filter(pk=self.pk).update(
                ytd_sales=ytd_sales,
                outstanding_invoices=outstanding_count,
                outstanding_amount=outstanding_amount,
                overdue_amount=overdue_amount,
                updated_at=timezone.now()
            )
            
        except Exception as e:
            print(f"Error updating calculated fields for customer {self.id}: {e}")

class CustomerContact(models.Model):
    """Alternative: Separate model for contacts if needed"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="contact_persons")
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_primary', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.customer.company_name})"
















from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class Invoice(models.Model):
    """Invoice model linked to Customer"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('pending', 'Pending'),
        ('overdue', 'Overdue'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    CURRENCY_CHOICES = [
        ('AED', 'AED (UAE Dirham)'),
        ('USD', 'USD (US Dollar)'),
        ('EUR', 'EUR (Euro)'),
        ('GBP', 'GBP (British Pound)'),
        ('SAR', 'SAR (Saudi Riyal)'),
        ('INR', 'INR (Indian Rupee)'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
        ('cheque', 'Cheque'),
        ('online_payment', 'Online Payment'),
    ]
    
    # Invoice identification
    invoice_number = models.CharField(max_length=50, unique=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    
    # Customer relationship - ADD THIS FOREIGN KEY
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.PROTECT,  # Prevent deleting customer with invoices
        related_name='invoices',
        null=True,  # Temporarily allow null for existing data
        blank=True
    )
    
    # Keep customer info as backup (denormalized for performance)
    customer_id_backup = models.CharField(max_length=100, blank=True, null=True)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    billing_address = models.TextField()
    
    # Dates
    date = models.DateField()  # Invoice date
    due_date = models.DateField()
    added_date = models.DateField(auto_now_add=True)
    
    # Financial details
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='AED')
    payment_terms = models.PositiveIntegerField(default=30)  # days
    
    sub_total = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_overdue = models.BooleanField(default=False)
    
    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    
    # Items and payments (stored as JSON)
    items = models.JSONField(default=list, blank=True)  # List of invoice items
    payment_history = models.JSONField(default=list, blank=True)  # List of payments
    notes = models.JSONField(default=list, blank=True)  # List of notes
    
    # Tenant-specific custom fields
    custom_data = models.JSONField(default=dict, blank=True)
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['customer']),  # Added index
            models.Index(fields=['customer_name']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.customer_name}"
    
    def save(self, *args, **kwargs):
        # If we have a customer object, populate customer info
        if self.customer:
            if not self.customer_name:
                self.customer_name = self.customer.company_name
            if not self.customer_email:
                self.customer_email = self.customer.email
            if not self.customer_phone:
                self.customer_phone = self.customer.phone
            if not self.billing_address:
                self.billing_address = self.customer.billing_address
            if not self.customer_id_backup:
                self.customer_id_backup = self.customer.customer_id
        
        # Auto-calculate outstanding amount
        self.outstanding_amount = self.total - self.paid_amount
        
        # Check if overdue
        from django.utils import timezone
        
        if self.due_date:
            # Ensure due_date is a date object
            if isinstance(self.due_date, str):
                try:
                    from datetime import datetime as dt
                    if '-' in self.due_date:
                        self.due_date = dt.strptime(self.due_date, '%Y-%m-%d').date()
                    else:
                        self.due_date = timezone.now().date()
                except (ValueError, TypeError):
                    self.due_date = timezone.now().date()
            
            # Now compare dates
            if self.status in ['sent', 'pending'] and self.due_date < timezone.now().date():
                self.is_overdue = True
                self.status = 'overdue'
            else:
                self.is_overdue = False
        
        super().save(*args, **kwargs)
    
    def add_payment(self, amount, method, reference=None, date=None):
        """Add a payment to payment history"""
        from django.utils import timezone
        
        payment = {
            'payment_id': f'pay-{len(self.payment_history) + 1:03d}',
            'date': date or timezone.now().date().isoformat(),
            'amount': str(amount),
            'method': method,
            'reference': reference
        }
        
        self.payment_history.append(payment)
        self.paid_amount += Decimal(str(amount))
        self.outstanding_amount = self.total - self.paid_amount
        
        # Update status if fully paid
        if self.outstanding_amount <= 0:
            self.status = 'paid'
        
        self.save()
        return payment
    
    def update_customer_stats(self):
        """Update customer's financial statistics when invoice changes"""
        if self.customer:
            # Recalculate all customer stats
            self.customer.update_calculated_fields()





from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()

class Task(models.Model):
    """Task model linked to leads, customers, and invoices"""
    
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('blocked', 'Blocked'),
        ('cancelled', 'Cancelled'),
    ]
    
    RELATED_TYPE_CHOICES = [
        ('lead', 'Lead'),
        ('customer', 'Customer'),
        ('invoice', 'Invoice'),
        ('none', 'None'),
    ]
    
    RECURRENCE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    # Basic task info
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks'
    )
    
    # Relations to other models
    related_type = models.CharField(
        max_length=20, 
        choices=RELATED_TYPE_CHOICES, 
        default='none'
    )
    related_lead = models.ForeignKey(
        'Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    related_customer = models.ForeignKey(
        'Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    related_invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    
    # Dates
    due_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    
    # Task properties
    priority = models.CharField(
        max_length=20, 
        choices=PRIORITY_CHOICES, 
        default='medium'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='todo'
    )
    
    # Recurring tasks
    recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(
        max_length=20, 
        choices=RECURRENCE_CHOICES, 
        null=True, 
        blank=True
    )
    next_due_date = models.DateField(null=True, blank=True)
    
    # Dynamic data (JSON fields)
    tags = models.JSONField(default=list, blank=True)
    comments = models.JSONField(default=list, blank=True)
    custom_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['due_date', 'priority', 'created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['due_date']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['related_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # Auto-set completed_date when status changes to 'done'
        if self.status == 'done' and not self.completed_date:
            self.completed_date = timezone.now().date()
        elif self.status != 'done' and self.completed_date:
            self.completed_date = None
        
        # Auto-update related_type based on which relation is set
        if self.related_lead:
            self.related_type = 'lead'
        elif self.related_customer:
            self.related_type = 'customer'
        elif self.related_invoice:
            self.related_type = 'invoice'
        else:
            self.related_type = 'none'
        
        # Handle recurring tasks
        if self.recurring and self.status == 'done' and self.recurrence_pattern:
            self.create_next_recurrence()
        
        super().save(*args, **kwargs)
    
    def create_next_recurrence(self):
        """Create next occurrence for recurring task"""
        from datetime import timedelta
        
        if not self.recurrence_pattern:
            return
        
        # Calculate next due date
        next_due = self.due_date
        
        if self.recurrence_pattern == 'daily':
            next_due = self.due_date + timedelta(days=1)
        elif self.recurrence_pattern == 'weekly':
            next_due = self.due_date + timedelta(weeks=1)
        elif self.recurrence_pattern == 'monthly':
            # Add 30 days for monthly (simplified)
            next_due = self.due_date + timedelta(days=30)
        elif self.recurrence_pattern == 'quarterly':
            next_due = self.due_date + timedelta(days=90)
        elif self.recurrence_pattern == 'yearly':
            next_due = self.due_date + timedelta(days=365)
        
        # Create new task for next recurrence
        new_task = Task.objects.create(
            title=self.title,
            description=self.description,
            assigned_to=self.assigned_to,
            created_by=self.created_by,
            related_type=self.related_type,
            related_lead=self.related_lead,
            related_customer=self.related_customer,
            related_invoice=self.related_invoice,
            due_date=next_due,
            priority=self.priority,
            status='todo',
            recurring=self.recurring,
            recurrence_pattern=self.recurrence_pattern,
            tags=self.tags.copy() if self.tags else [],
            comments=[]  # Start fresh with comments
        )
        
        return new_task
    
    def is_overdue(self):
        """Check if task is overdue"""
        if self.status in ['done', 'cancelled']:
            return False
        return self.due_date < timezone.now().date()
    
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue():
            return 0
        delta = timezone.now().date() - self.due_date
        return delta.days
    
    def days_until_due(self):
        """Calculate days until due date"""
        if self.status in ['done', 'cancelled']:
            return None
        delta = self.due_date - timezone.now().date()
        return delta.days
    
    def add_comment(self, text, user):
        """Add a comment to the comments array"""
        comment = {
            "id": len(self.comments) + 1,
            "text": text,
            "user_id": user.id,
            "user_name": user.username,
            "created_at": timezone.now().isoformat()
        }
        self.comments.append(comment)
        self.save(update_fields=['comments', 'updated_at'])
        return comment
    
    def get_related_object(self):
        """Get the related object based on related_type"""
        if self.related_type == 'lead' and self.related_lead:
            return self.related_lead
        elif self.related_type == 'customer' and self.related_customer:
            return self.related_customer
        elif self.related_type == 'invoice' and self.related_invoice:
            return self.related_invoice
        return None
    
    def get_related_info(self):
        """Get information about the related object"""
        related = self.get_related_object()
        if not related:
            return None
        
        if isinstance(related, Lead):
            return {
                'type': 'lead',
                'id': related.id,
                'name': related.name,
                'company': related.company,
                'status': related.status
            }
        elif isinstance(related, Customer):
            return {
                'type': 'customer',
                'id': related.id,
                'name': related.company_name,
                'customer_name': related.customer_name,
                'email': related.email
            }
        elif isinstance(related, Invoice):
            return {
                'type': 'invoice',
                'id': related.id,
                'number': related.invoice_number,
                'customer_name': related.customer_name,
                'total': str(related.total),
                'status': related.status
            }
        return None

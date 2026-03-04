from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import *
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import now
from django.db.models import Sum, Count
import uuid



User = get_user_model()


class NavigationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema()

        operations = (
            schema.get("navigation", {})
                  .get("operations", {})
        )

        return Response({
            "success": True,
            "operations": operations
        })




class SchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "tenant": request.tenant.name,
            "schema": request.tenant.get_leads_schema()
        })




class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        total_leads = Lead.objects.count()
        total_customers = Customer.objects.count()
        total_invoices = Invoice.objects.count()
        total_inventory = InventoryItem.objects.count()  # ✅ FIXED

        total_revenue = Invoice.objects.filter(
            status__iexact="paid"
        ).aggregate(total=Sum("total"))["total"] or 0

        outstanding = Invoice.objects.filter(
            status__in=["sent", "overdue"]
        ).aggregate(total=Sum("total"))["total"] or 0

        recent_invoices = Invoice.objects.order_by("-created_at")[:5]
        recent_leads = Lead.objects.order_by("-created_at")[:5]

        return Response({
            "summary": {
                "total_leads": total_leads,
                "total_customers": total_customers,
                "total_invoices": total_invoices,
                "total_inventory": total_inventory,
                "total_revenue": float(total_revenue),
                "outstanding": float(outstanding),
            },
            "recent_invoices": [
                {
                    "id": i.id,
                    "number": i.number,
                    "customer": i.customer.company if i.customer else "Custom",
                    "total": float(i.total),
                    "status": i.status
                }
                for i in recent_invoices
            ],
            "recent_leads": [
                {
                    "id": l.id,
                    "name": l.name,
                    "company": l.company
                }
                for l in recent_leads
            ]
        })


class LeadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("leads", {})
        columns = schema.get("table_columns", [])

        leads = Lead.objects.all().select_related("assigned_to")

        data = []
        for lead in leads:
            row = {"id": lead.id}

            for col in columns:
                if hasattr(lead, col):
                    value = getattr(lead, col)
                    if col == "assigned_to" and value:
                        row[col] = value.username
                    else:
                        row[col] = value
                else:
                    row[col] = lead.extra_data.get(col)

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })
    


class LeadCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        schema = request.tenant.get_leads_schema()
        form_fields = schema.get("form_fields", [])
        fields = schema.get("fields", [])

        field_map = {f["key"]: f for f in fields}
        payload = request.data

        lead_data = {}
        extra_data = {}

        # basic required validation (simple on purpose)
        errors = []
        for key in form_fields:
            config = field_map.get(key, {})
            if config.get("required") and not payload.get(key):
                errors.append(f"{config.get('label', key)} is required")

        if errors:
            return Response({"errors": errors}, status=400)

        for key in form_fields:
            value = payload.get(key)
            if value is None:
                continue

            if hasattr(Lead, key):
                if key == "assigned_to":
                    try:
                        value = User.objects.get(id=value)
                    except User.DoesNotExist:
                        value = None
                lead_data[key] = value
            else:
                extra_data[key] = value

        lead = Lead.objects.create(
            **lead_data,
            extra_data=extra_data,
            created_by=request.user
        )

        return Response({
            "success": True,
            "lead_id": lead.id
        }, status=201)
    



class LeadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)

        data = {
            "id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company,
            "assigned_to": lead.assigned_to.username if lead.assigned_to else None,
            "created_by": lead.created_by.username if lead.created_by else None,
            "extra_data": lead.extra_data,
            "notes": lead.notes,
            "created_at": lead.created_at,
            "updated_at": lead.updated_at,
        }

        return Response({
            "success": True,
            "lead": data
        })
    

class LeadUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)

        schema = request.tenant.get_leads_schema()
        fields = schema.get("fields", [])
        field_map = {f["key"]: f for f in fields}

        payload = request.data

        for key, value in payload.items():
            if key not in field_map:
                continue

            # core model field
            if hasattr(Lead, key):
                if key == "assigned_to":
                    try:
                        value = User.objects.get(id=value)
                    except User.DoesNotExist:
                        value = None

                setattr(lead, key, value)

            # custom field → extra_data
            else:
                lead.extra_data[key] = value

        lead.save()

        return Response(
            {"success": True, "message": "Lead updated"},
            status=status.HTTP_200_OK
        )
    


from django.utils import timezone

class LeadAddNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)

        text = request.data.get("text")
        if not text:
            return Response(
                {"error": "Note text is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        notes = lead.notes or []

        new_note = {
            "id": len(notes) + 1,
            "text": text,
            "user_id": request.user.id,
            "user_name": request.user.username,
            "created_at": timezone.now().isoformat()
        }

        notes.append(new_note)
        lead.notes = notes
        lead.save(update_fields=["notes"])

        return Response({
            "success": True,
            "note": new_note
        }, status=status.HTTP_201_CREATED)


class LeadDeleteNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, note_id):
        lead = get_object_or_404(Lead, pk=pk)

        notes = lead.notes or []
        updated_notes = [n for n in notes if n.get("id") != note_id]

        if len(notes) == len(updated_notes):
            return Response(
                {"error": "Note not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        lead.notes = updated_notes
        lead.save(update_fields=["notes"])

        return Response({
            "success": True,
            "message": "Note deleted"
        })



class LeadDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        lead.delete()

        return Response({
            "success": True,
            "message": "Lead deleted successfully"
        }, status=status.HTTP_200_OK)

















from .models import Customer


class CustomerSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("customers", {})
        return Response({
            "success": True,
            "schema": schema
        })


class CustomerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("customers", {})
        columns = schema.get("table_columns", [])

        customers = Customer.objects.all().select_related("assigned_to")

        data = []

        for customer in customers:
            row = {"id": customer.id}

            for col in columns:
                if hasattr(customer, col):
                    value = getattr(customer, col)

                    if col == "assigned_to" and value:
                        row[col] = value.username
                    else:
                        row[col] = value
                else:
                    # 👇 THIS IS THE IMPORTANT PART
                    row[col] = customer.extra_data.get(col)

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })



class CustomerCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data

        core_fields = [
            "company",
            "contact_name",
            "email",
            "phone",
            "status",
            "assigned_to",
        ]

        customer_data = {}
        extra_data = {}

        for key, value in payload.items():
            if key in core_fields:
            
                if key == "assigned_to" and value:
                    try:
                        value = User.objects.get(id=value)
                    except User.DoesNotExist:
                        value = None
        
                customer_data[key] = value
        
            elif key == "extra_data":
                extra_data = value   # 👈 directly assign
        
            elif key != "notes":
                extra_data[key] = value


        customer = Customer.objects.create(
            **customer_data,
            extra_data=extra_data,
            notes=payload.get("notes", []),
            created_by=request.user
        )

        return Response({
            "success": True,
            "customer_id": customer.id
        }, status=201)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)

        data = {
            "id": customer.id,
            "company": customer.company,
            "contact_name": customer.contact_name,
            "email": customer.email,
            "phone": customer.phone,
            "status": customer.status,
            "assigned_to": customer.assigned_to.id if customer.assigned_to else None,
            "assigned_to_name": customer.assigned_to.username if customer.assigned_to else None,
            "created_by": customer.created_by.username if customer.created_by else None,
            "extra_data": customer.extra_data,
            "notes": customer.notes,
            "created_at": customer.created_at,
            "updated_at": customer.updated_at,
        }

        return Response({
            "success": True,
            "customer": data
        })
    

class CustomerUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        payload = request.data

        core_fields = [
            "company",
            "contact_name",
            "email",
            "phone",
            "status",
            "assigned_to",
        ]

        for key, value in payload.items():
            if key in core_fields:

                if key == "assigned_to":
                    if value:
                        try:
                            value = User.objects.get(id=value)
                        except User.DoesNotExist:
                            value = None
                    else:
                        value = None

                setattr(customer, key, value)

            elif key not in ["notes", "extra_data"]:
                customer.extra_data[key] = value

        customer.save()

        return Response({
            "success": True,
            "message": "Customer updated"
        })
 



class CustomerAddNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)

        text = request.data.get("text")
        if not text:
            return Response(
                {"error": "Note text is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        note = {
            "id": str(uuid.uuid4()),
            "text": text,
            "created_by": request.user.id,
            "user_name": request.user.username,
            "created_at": timezone.now().isoformat()
        }

        notes = customer.notes or []
        notes.append(note)

        customer.notes = notes   # 🔥 MUST reassign
        customer.save()

        return Response(
            {"success": True, "note": note},
            status=status.HTTP_201_CREATED
        )


class CustomerDeleteNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, note_id):
        customer = get_object_or_404(Customer, pk=pk)

        notes = customer.notes or []
        updated_notes = [n for n in notes if str(n.get("id")) != str(note_id)]

        if len(notes) == len(updated_notes):
            return Response(
                {"error": "Note not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        customer.notes = updated_notes
        customer.save()

        return Response(
            {"success": True, "message": "Note deleted"},
            status=status.HTTP_200_OK
        )


class CustomerDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        customer.delete()

        return Response(
            {"success": True, "message": "Customer deleted"},
            status=status.HTTP_200_OK
        )




from django.db.models import Prefetch


class AccountListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = Account.objects.select_related("parent").all()

        data = []

        for acc in accounts:
            data.append({
                "id": acc.id,
                "code": acc.code,
                "name": acc.name,
                "type": acc.type,
                "description": acc.description,
                "vat_applicable": acc.vat_applicable,
                "parent": acc.parent.code if acc.parent else None,
                "parent_id": acc.parent.id if acc.parent else None,
            })

        return Response({
            "success": True,
            "accounts": data
        })


class AccountCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data

        parent = None
        if payload.get("parent_id"):
            parent = get_object_or_404(Account, id=payload["parent_id"])

        account = Account.objects.create(
            code=payload["code"],
            name=payload["name"],
            type=payload["type"],
            description=payload.get("description"),
            vat_applicable=payload.get("vat_applicable", False),
            parent=parent,
            created_by=request.user,
        )

        return Response({
            "success": True,
            "id": account.id
        }, status=201)
    


class AccountUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        account = get_object_or_404(Account, pk=pk)
        payload = request.data

        account.code = payload.get("code", account.code)
        account.name = payload.get("name", account.name)
        account.type = payload.get("type", account.type)
        account.description = payload.get("description", account.description)
        account.vat_applicable = payload.get("vat_applicable", account.vat_applicable)

        parent_id = payload.get("parent_id")
        if parent_id:
            try:
                parent = Account.objects.get(id=parent_id)
                account.parent = parent
            except Account.DoesNotExist:
                account.parent = None
        else:
            account.parent = None

        account.save()

        return Response({
            "success": True,
            "message": "Account updated"
        }, status=200)


class AccountDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        account = get_object_or_404(Account, pk=pk)
        account.delete()
        return Response({"success": True})
    







class ExpenseSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("expenses", {})
        return Response({
            "success": True,
            "schema": schema
        })





class ExpenseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema().get("expenses", {})
        columns = schema.get("table_columns", [])

        expenses = Expense.objects.select_related(
            "vendor",
            "account",
            "payment_account"
        )

        rows = []

        for expense in expenses:

            row = {"id": expense.id}

            for col in columns:

                # ✅ Vendor
                if col == "vendor_name":
                    row[col] = (
                        expense.vendor.company
                        if expense.vendor else None
                    )

                # ✅ Expense Account
                elif col == "account_name":
                    row[col] = (
                        f"{expense.account.code} - {expense.account.name}"
                        if expense.account else None
                    )

                # ✅ Payment Account
                elif col == "payment_account_name":
                    row[col] = (
                        f"{expense.payment_account.code} - {expense.payment_account.name}"
                        if expense.payment_account else None
                    )

                # ✅ Model fields
                elif hasattr(expense, col):
                    value = getattr(expense, col)
                    row[col] = (
                        float(value) if isinstance(value, Decimal) else value
                    )

                # ✅ Extra fields
                else:
                    row[col] = (expense.extra_data or {}).get(col)

            rows.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": rows
        })


class ExpenseCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        try:
            payload = request.data

            # =========================
            # REQUIRED VALIDATIONS
            # =========================

            if not payload.get("expense_number"):
                return Response({
                    "success": False,
                    "error": "Expense number required"
                }, status=400)

            if not payload.get("account"):
                return Response({
                    "success": False,
                    "error": "Expense account required"
                }, status=400)

            if not payload.get("payment_account"):
                return Response({
                    "success": False,
                    "error": "Payment account required"
                }, status=400)

            # =========================
            # FETCH VENDOR (🔥 THIS WAS MISSING)
            # =========================

            vendor = None
            if payload.get("vendor"):
                vendor = get_object_or_404(
                    Vendor,
                    id=payload.get("vendor")
                )

            # =========================
            # FETCH ACCOUNTS
            # =========================

            expense_account = get_object_or_404(
                Account,
                id=payload.get("account"),
                type="Expense"
            )

            payment_account = get_object_or_404(
                Account,
                id=payload.get("payment_account"),
                type="Asset"
            )

            # =========================
            # SAFE DECIMAL CONVERSION
            # =========================

            amount = Decimal(str(payload.get("amount", 0)))

            # =========================
            # CREATE EXPENSE
            # =========================

            expense = Expense.objects.create(
                expense_number=payload.get("expense_number"),
                date=payload.get("date"),
                vendor=vendor,  # ✅ FIXED
                currency=payload.get("currency", "AED"),
                amount=amount,
                vat_applicable=payload.get("vat_applicable", True),
                account=expense_account,
                payment_account=payment_account,
                status=payload.get("status", "DRAFT"),
                notes=payload.get("notes"),
                extra_data=payload.get("extra_data", {}),
                created_by=request.user
            )

            # =========================
            # AUTO JOURNAL IF POSTED
            # =========================

            journal_id = None

            if expense.status == "POSTED":

                journal_entries = [
                    {
                        "account": expense.account.id,
                        "debit": float(expense.total),
                        "credit": 0
                    },
                    {
                        "account": expense.payment_account.id,
                        "debit": 0,
                        "credit": float(expense.total)
                    }
                ]

                journal = ManualJournal.objects.create(
                    date=expense.date,
                    currency=expense.currency,
                    status="Posted",
                    notes=f"Expense Payment - {expense.expense_number}",
                    entries=journal_entries,
                    created_by=request.user
                )

                journal_id = journal.id

            return Response({
                "success": True,
                "expense_id": expense.id,
                "journal_id": journal_id
            }, status=201)

        except Exception as e:
            return Response({
                "success": False,
                "error": str(e)
            }, status=400)





class ExpensePostView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        expense = get_object_or_404(Expense, pk=pk)

        if expense.status == "POSTED":
            return Response({
                "success": False,
                "error": "Expense already posted"
            }, status=400)

        if not expense.payment_account:
            return Response({
                "success": False,
                "error": "Payment account required"
            }, status=400)

        # Update status
        expense.status = "POSTED"
        expense.save()

        # Create journal
        journal_entries = [
            {
                "account": expense.account.id,
                "debit": float(expense.total),
                "credit": 0
            },
            {
                "account": expense.payment_account.id,
                "debit": 0,
                "credit": float(expense.total)
            }
        ]

        journal = ManualJournal.objects.create(
            date=expense.date,
            currency=expense.currency,
            status="Posted",
            notes=f"Expense Payment - {expense.expense_number}",
            entries=journal_entries,
            created_by=request.user
        )

        return Response({
            "success": True,
            "journal_id": journal.id
        })


class AccountListByTypeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account_type = request.query_params.get("type")

        if not account_type:
            return Response({
                "success": False,
                "message": "Account type required"
            }, status=400)

        accounts = Account.objects.filter(type=account_type)

        data = [
            {
                "id": acc.id,
                "code": acc.code,
                "name": acc.name,
                "type": acc.type
            }
            for acc in accounts
        ]

        return Response({
            "success": True,
            "accounts": data
        })


class ExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        expense = get_object_or_404(
            Expense.objects.select_related(
                "vendor",
                "account",
                "payment_account"
            ),
            pk=pk
        )

        return Response({
            "success": True,
            "expense": {
                "id": expense.id,
                "expense_number": expense.expense_number,
                "date": expense.date,

                # Vendor
                "vendor": expense.vendor.id if expense.vendor else None,
                "vendor_name": (
                    expense.vendor.company
                    if expense.vendor else None
                ),

                "currency": expense.currency,
                "amount": float(expense.amount),
                "vat_applicable": expense.vat_applicable,
                "vat_amount": float(expense.vat_amount),
                "total": float(expense.total),

                # Expense Account
                "account": expense.account.id if expense.account else None,
                "account_name": (
                    f"{expense.account.code} - {expense.account.name}"
                    if expense.account else None
                ),

                # 🔥 Payment Account (THIS replaces payment_method)
                "payment_account": expense.payment_account.id if expense.payment_account else None,
                "payment_account_name": (
                    f"{expense.payment_account.code} - {expense.payment_account.name}"
                    if expense.payment_account else None
                ),

                "status": expense.status,
                "notes": expense.notes,
                "extra_data": expense.extra_data,
                "created_by": expense.created_by.username if expense.created_by else None,
                "created_at": expense.created_at,
                "updated_at": expense.updated_at,
            }
        })



class ExpenseUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, pk):

        expense = get_object_or_404(Expense, pk=pk)

        if expense.status == "POSTED":
            return Response({
                "success": False,
                "error": "Posted expenses cannot be edited"
            }, status=400)

        payload = request.data

        if "amount" in payload:
            expense.amount = Decimal(str(payload["amount"]))

        if "account" in payload:
            expense.account = get_object_or_404(
                Account,
                id=payload["account"]
            )

        if "payment_account" in payload:
            expense.payment_account = get_object_or_404(
                Account,
                id=payload["payment_account"]
            )

        expense.notes = payload.get("notes", expense.notes)
        expense.vat_applicable = payload.get(
            "vat_applicable",
            expense.vat_applicable
        )

        expense.save()

        return Response({
            "success": True,
            "message": "Expense updated"
        })
import pdfplumber
import re
from datetime import datetime

class ExpenseInvoiceImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return Response({
                "success": False,
                "error": "No file uploaded"
            }, status=400)

        try:
            full_text = ""
            items = []

            # ===============================
            # EXTRACT TEXT + TABLES
            # ===============================

            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:

                    # Extract raw text
                    full_text += page.extract_text() or ""

                    # Extract tables
                    tables = page.extract_tables()

                    for table in tables:
                        for row in table:
                            if not row:
                                continue

                            row_text = " ".join(
                                str(cell) for cell in row if cell
                            )

                            # Detect rows that contain qty + price
                            match = re.search(
                                r"(.+?)\s+(\d+)\s+([\d,]+\.\d{2})",
                                row_text
                            )

                            if match:
                                description = match.group(1).strip()
                                qty = int(match.group(2))
                                price = float(match.group(3).replace(",", ""))

                                items.append({
                                    "description": description,
                                    "quantity": qty,
                                    "unit_price": price
                                })

            text = full_text.replace("\n", " ")
            text_lower = text.lower()

            # ===============================
            # SMART FIELD FINDER
            # ===============================

            def find_pattern(patterns):
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
                return ""

            # ===============================
            # INVOICE NUMBER
            # ===============================

            year = now().year

            count = ExpenseInvoice.objects.filter(date__year=year).count() + 1

            invoice_number = f"EXP-{year}-{str(count).zfill(4)}"

            # ===============================
            # DATE EXTRACTION
            # ===============================

            def extract_labeled_date(labels):
                for label in labels:
                    pattern = rf"{label}[\s:]*([\d./-]+)"
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return match.group(1)
                return ""

            invoice_date = extract_labeled_date([
                "invoice date",
                "issued on",
                "bill date",
                "date"
            ])

            due_date = extract_labeled_date([
                "due date",
                "payment due",
                "pay by"
            ])

            # Fallback: detect all date patterns
            if not invoice_date:
                all_dates = re.findall(
                    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
                    text
                )
                if all_dates:
                    invoice_date = all_dates[0]
                    if len(all_dates) > 1:
                        due_date = all_dates[1]

            # ===============================
            # VENDOR DETECTION
            # ===============================

            vendor = find_pattern([
                r"(?:vendor|supplier|from|sold\s*by)[\s:]*([A-Za-z0-9 &.,-]+)",
            ])

            # ===============================
            # AMOUNT EXTRACTION
            # ===============================

            def extract_amount(labels):
                for label in labels:
                    pattern = rf"{label}[\s:]*([\d,]+\.\d{{2}})"
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return float(match.group(1).replace(",", ""))
                return 0

            subtotal = extract_amount([
                "subtotal", "sub total", "net amount"
            ])

            vat = extract_amount([
                "vat", "tax", "vat amount"
            ])

            total = extract_amount([
                "grand total", "total amount", "amount payable", "total"
            ])

            # ===============================
            # AUTO CALCULATE IF MISSING
            # ===============================

            if items and not subtotal:
                subtotal = sum(
                    item["quantity"] * item["unit_price"]
                    for item in items
                )

            if subtotal and not vat:
                vat = round(subtotal * 0.05, 2)

            if subtotal and not total:
                total = round(subtotal + vat, 2)

            # ===============================
            # CONFIDENCE SCORE
            # ===============================

            score_fields = [
                invoice_number,
                invoice_date,
                total
            ]

            filled = sum(bool(f) for f in score_fields)
            confidence = int((filled / len(score_fields)) * 100)

            extracted_data = {
                "invoice_number": invoice_number,
                "vendor_name": vendor,
                "date": invoice_date,
                "due_date": due_date,
                "items": items,
                "subtotal": subtotal,
                "vat": vat,
                "total": total,
                "confidence": confidence
            }

            return Response({
                "success": True,
                "data": extracted_data
            })

        except Exception as e:
            return Response({
                "success": False,
                "error": str(e)
            }, status=500)
        
        

class ExpenseDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        expense.delete()

        return Response({
            "success": True,
            "message": "Expense deleted"
        })







class InventorySchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("inventories", {})
        return Response({
            "success": True,
            "schema": schema
        })



class InventoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("inventories", {})
        columns = schema.get("table_columns", [])

        items = InventoryItem.objects.all()

        data = []

        for item in items:
            row = {"id": item.id}

            inventory_value = Decimal(str(item.current_quantity)) * Decimal(str(item.cost_price))

            for col in columns:
                if col == "inventory_value":
                    row[col] = str(inventory_value)
                elif hasattr(item, col):
                    value = getattr(item, col)
                    row[col] = str(value) if isinstance(value, Decimal) else value
                else:
                    row[col] = None

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })



class InventoryCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        try:
            payload = request.data

            item_code = payload.get("item_code")
            item_name = payload.get("item_name")

            purchase_quantity = Decimal(str(payload.get("purchase_quantity", 0)))
            purchase_price = Decimal(str(payload.get("purchase_price", 0)))

            if not item_code:
                return Response({"error": "Item code required"}, status=400)

            existing_item = InventoryItem.objects.filter(
                item_code=item_code
            ).first()

            # ==========================================
            # CASE 1: EXISTING ITEM → ADD STOCK
            # ==========================================

            if existing_item:

                if purchase_quantity <= 0:
                    return Response({
                        "error": "Purchase quantity required"
                    }, status=400)

                if purchase_price < 0:
                    return Response({"error": "Invalid purchase price"}, status=400)

                old_qty = Decimal(str(existing_item.current_quantity))
                old_cost = Decimal(str(existing_item.cost_price))

                total_old_value = old_qty * old_cost
                total_new_value = purchase_quantity * purchase_price

                new_total_qty = old_qty + purchase_quantity

                new_avg_cost = (
                    (total_old_value + total_new_value) / new_total_qty
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                existing_item.current_quantity = new_total_qty
                existing_item.cost_price = new_avg_cost
                existing_item.save()

                return Response({
                    "success": True,
                    "message": "Stock added successfully",
                    "new_quantity": str(new_total_qty),
                    "new_cost_price": str(new_avg_cost)
                })

            # ==========================================
            # CASE 2: NEW PRODUCT CREATION
            # ==========================================

            # For new product, name is required
            if not item_name:
                return Response({"error": "Item name required"}, status=400)

            # For new product, unit_of_measure is required
            if not payload.get("unit_of_measure"):
                return Response({"error": "Unit of measure required"}, status=400)

            # If no opening stock provided → default zero
            if purchase_quantity <= 0:
                purchase_quantity = Decimal("0.00")
                purchase_price = Decimal("0.00")

            if purchase_price < 0:
                return Response({"error": "Invalid purchase price"}, status=400)

            item = InventoryItem.objects.create(
                item_code=item_code,
                item_name=item_name,
                category=payload.get("category"),
                description=payload.get("description"),
                unit_of_measure=payload.get("unit_of_measure"),

                cost_price=purchase_price,
                current_quantity=purchase_quantity,

                selling_price=Decimal(str(payload.get("selling_price", 0))),
                minimum_quantity=Decimal(str(payload.get("minimum_quantity", 0))),
                warehouse=payload.get("warehouse"),
                status=payload.get("status", "ACTIVE"),

                created_by=request.user
            )

            return Response({
                "success": True,
                "message": "New product created",
                "inventory_id": item.id
            }, status=201)

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=400)



class InventoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        item = get_object_or_404(InventoryItem, pk=pk)

        current_qty = Decimal(str(item.current_quantity))
        cost_price = Decimal(str(item.cost_price))
        inventory_value = (current_qty * cost_price).quantize(
            Decimal("0.01")
        )

        # 🔥 Get transactions
        transactions = item.transactions.order_by("-created_at")

        transaction_data = []

        for tx in transactions:

            total_cost = (
                Decimal(str(tx.quantity)) *
                Decimal(str(tx.unit_cost))
            ).quantize(Decimal("0.01"))

            transaction_data.append({
                "id": tx.id,
                "type": tx.transaction_type,
                "quantity": str(tx.quantity),
                "unit_cost": str(tx.unit_cost),
                "total_cost": str(total_cost),
                "reference": tx.reference,
                "date": tx.created_at,
            })

        data = {
            "id": item.id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "category": item.category,
            "description": item.description,
            "unit_of_measure": item.unit_of_measure,

            # STOCK SUMMARY
            "current_quantity": str(current_qty),
            "average_cost": str(cost_price),
            "inventory_value": str(inventory_value),

            # SALES DATA
            "selling_price": str(item.selling_price),

            # CONTROL
            "minimum_quantity": str(item.minimum_quantity),
            "warehouse": item.warehouse,
            "status": item.status,

            # 🔥 FULL TRANSACTION HISTORY
            "transactions": transaction_data,

            "created_at": item.created_at,
            "last_updated": item.last_updated,
        }

        return Response({
            "success": True,
            "inventory": data
        })


from decimal import Decimal, InvalidOperation
from django.utils import timezone


class InventoryUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):

        item = get_object_or_404(InventoryItem, pk=pk)

        allowed_fields = [
            "item_name",
            "category",
            "description",
            "unit_of_measure",
            "selling_price",
            "tax_applicable",
            "tax_rate",
            "minimum_quantity",
            "warehouse",
            "status"
        ]

        try:

            # ==========================================
            # TEXT FIELDS
            # ==========================================

            for field in ["item_name", "category", "description", "unit_of_measure", "warehouse", "status"]:
                if field in request.data:
                    setattr(item, field, request.data.get(field))

            # ==========================================
            # DECIMAL FIELDS
            # ==========================================

            if "selling_price" in request.data:
                try:
                    item.selling_price = Decimal(
                        str(request.data.get("selling_price"))
                    )
                except (InvalidOperation, TypeError):
                    return Response(
                        {"error": "Invalid selling price"},
                        status=400
                    )

            if "minimum_quantity" in request.data:
                try:
                    item.minimum_quantity = Decimal(
                        str(request.data.get("minimum_quantity"))
                    )
                except (InvalidOperation, TypeError):
                    return Response(
                        {"error": "Invalid minimum quantity"},
                        status=400
                    )

            # ==========================================
            # TAX LOGIC
            # ==========================================

            if "tax_applicable" in request.data:
                item.tax_applicable = bool(request.data.get("tax_applicable"))

            if item.tax_applicable:
                if "tax_rate" in request.data:
                    try:
                        item.tax_rate = Decimal(
                            str(request.data.get("tax_rate"))
                        )
                    except (InvalidOperation, TypeError):
                        return Response(
                            {"error": "Invalid tax rate"},
                            status=400
                        )
            else:
                item.tax_rate = Decimal("0.00")

            # ==========================================
            # PROTECT COST & STOCK
            # ==========================================

            # We intentionally DO NOT allow:
            # - cost_price
            # - current_quantity
            # These must change only via transactions

            item.last_updated = timezone.now()
            item.save()

            return Response({
                "success": True,
                "message": "Inventory updated successfully"
            })

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=400
            )

class InventoryDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        item = get_object_or_404(InventoryItem, pk=pk)
        item.delete()

        return Response({
            "success": True,
            "message": "Inventory deleted"
        })



class VendorSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("vendors", {})
        return Response({
            "success": True,
            "schema": schema
        })


class VendorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("vendors", {})
        columns = schema.get("table_columns", [])

        vendors = Vendor.objects.all().select_related("assigned_to")

        data = []

        for vendor in vendors:
            row = {"id": vendor.id}

            for col in columns:
                if hasattr(vendor, col):
                    value = getattr(vendor, col)

                    if col == "assigned_to" and value:
                        row[col] = value.username
                    else:
                        row[col] = value
                else:
                    row[col] = vendor.extra_data.get(col)

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })


class VendorCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data

        core_fields = [
            "company",
            "contact_name",
            "email",
            "phone",
            "status",
            "assigned_to",
        ]

        vendor_data = {}
        extra_data = {}

        for key, value in payload.items():

            if key in core_fields:

                if key == "assigned_to" and value:
                    try:
                        value = User.objects.get(id=value)
                    except User.DoesNotExist:
                        value = None

                vendor_data[key] = value

            elif key == "extra_data":
                extra_data = value

            elif key != "notes":
                extra_data[key] = value

        vendor = Vendor.objects.create(
            **vendor_data,
            extra_data=extra_data,
            notes=payload.get("notes", []),
            created_by=request.user
        )

        return Response({
            "success": True,
            "vendor_id": vendor.id
        }, status=201)



class VendorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        vendor = get_object_or_404(Vendor, pk=pk)

        data = {
            "id": vendor.id,
            "company": vendor.company,
            "contact_name": vendor.contact_name,
            "email": vendor.email,
            "phone": vendor.phone,
            "status": vendor.status,
            "assigned_to": vendor.assigned_to.id if vendor.assigned_to else None,
            "assigned_to_name": vendor.assigned_to.username if vendor.assigned_to else None,
            "created_by": vendor.created_by.username if vendor.created_by else None,
            "extra_data": vendor.extra_data,
            "notes": vendor.notes,
            "created_at": vendor.created_at,
            "updated_at": vendor.updated_at,
        }

        return Response({
            "success": True,
            "vendor": data
        })




class VendorUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        vendor = get_object_or_404(Vendor, pk=pk)
        payload = request.data

        core_fields = [
            "company",
            "contact_name",
            "email",
            "phone",
            "status",
            "assigned_to",
        ]

        for key, value in payload.items():

            if key in core_fields:

                if key == "assigned_to":
                    if value:
                        try:
                            value = User.objects.get(id=value)
                        except User.DoesNotExist:
                            value = None
                    else:
                        value = None

                setattr(vendor, key, value)

            elif key not in ["notes", "extra_data"]:
                vendor.extra_data[key] = value

        vendor.save()

        return Response({
            "success": True,
            "message": "Vendor updated"
        })



class VendorAddNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        vendor = get_object_or_404(Vendor, pk=pk)

        text = request.data.get("text")
        if not text:
            return Response(
                {"error": "Note text is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        note = {
            "id": str(uuid.uuid4()),
            "text": text,
            "created_by": request.user.id,
            "user_name": request.user.username,
            "created_at": timezone.now().isoformat()
        }

        notes = vendor.notes or []
        notes.append(note)

        vendor.notes = notes
        vendor.save()

        return Response(
            {"success": True, "note": note},
            status=status.HTTP_201_CREATED
        )



class VendorDeleteNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, note_id):
        vendor = get_object_or_404(Vendor, pk=pk)

        notes = vendor.notes or []
        updated_notes = [n for n in notes if str(n.get("id")) != str(note_id)]

        if len(notes) == len(updated_notes):
            return Response(
                {"error": "Note not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        vendor.notes = updated_notes
        vendor.save()

        return Response(
            {"success": True, "message": "Note deleted"},
            status=status.HTTP_200_OK
        )




class VendorDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        vendor = get_object_or_404(Vendor, pk=pk)
        vendor.delete()

        return Response(
            {"success": True, "message": "Vendor deleted"},
            status=status.HTTP_200_OK
        )





from django.db import transaction


class InvoiceSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("invoices", {})
        return Response({
            "success": True,
            "schema": schema
        })



# class InvoiceCreateView(APIView):
#     permission_classes = [IsAuthenticated]

#     @transaction.atomic
#     def post(self, request):

#         payload = request.data
#         items = payload.get("items", [])

#         customer_id = payload.get("customer")
#         add_as_customer = payload.get("add_as_customer", False)

#         customer = None
#         custom_details = payload.get("custom_details", {})

       
#         if customer_id:
#             customer = get_object_or_404(Customer, id=customer_id)

       
#         elif add_as_customer and custom_details:

#             customer = Customer.objects.create(
#                 company=custom_details.get("companyName"),
#                 contact_name=custom_details.get("contactPerson"),
#                 email=custom_details.get("email"),
#                 phone=custom_details.get("phone"),
#                 extra_data={
#                     "address": custom_details.get("address"),
#                     "trn": custom_details.get("trnNumber"),
#                 },
#                 created_by=request.user
#             )

#         invoice = Invoice.objects.create(
#             customer=customer,
#             custom_details=custom_details if not customer else {},
#             add_as_customer=add_as_customer,
#             date=payload.get("date"),
#             due_date=payload.get("due_date"),
#             status=payload.get("status", "draft"),
#             items=items,
#             extra_data=payload.get("extra_data", {}),
#             notes=payload.get("notes", []),
#             created_by=request.user
#         )

#         return Response({
#             "success": True,
#             "invoice_id": invoice.id,
#             "number": invoice.number
#         }, status=201)


class InvoiceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        try:
            payload = request.data
            items = payload.get("items", [])
            
            # 🔥 ADD THESE PRINT STATEMENTS
            print("\n" + "="*50)
            print("RECEIVED PAYLOAD:")
            print("="*50)
            print(f"Status: {payload.get('status')}")
            print(f"Items count: {len(items)}")
            print("\nItems with vat_included:")
            for i, item in enumerate(items):
                vat_included = item.get('vat_included', False)
                line_total = float(item.get('quantity', 0)) * float(item.get('price', 0))
                vat_amount = line_total * 0.05 if vat_included else 0
                print(f"  Item {i+1}:")
                print(f"    Description: {item.get('description')}")
                print(f"    Price: {item.get('price')}")
                print(f"    Quantity: {item.get('quantity')}")
                print(f"    vat_included: {vat_included}")
                print(f"    Line Total: {line_total}")
                print(f"    VAT Amount: {vat_amount}")
            
            print("\nCalculated totals from frontend:")
            print(f"  subtotal: {payload.get('subtotal')}")
            print(f"  vat: {payload.get('vat')}")
            print(f"  total: {payload.get('total')}")
            print("="*50 + "\n")

            if not items:
                return Response({"error": "At least one item required"}, status=400)

            customer_id = payload.get("customer")
            add_as_customer = payload.get("add_as_customer", False)

            customer = None
            custom_details = payload.get("custom_details", {})

            # 🔥 CASE 1: Existing Customer
            if customer_id:
                customer = get_object_or_404(Customer, id=customer_id)

            # 🔥 CASE 2: Save As Customer
            elif add_as_customer and custom_details:
                customer = Customer.objects.create(
                    company=custom_details.get("companyName"),
                    contact_name=custom_details.get("contactPerson"),
                    email=custom_details.get("email"),
                    phone=custom_details.get("phone"),
                    extra_data={
                        "address": custom_details.get("address"),
                        "trn": custom_details.get("trnNumber"),
                    },
                    created_by=request.user
                )

            # 🔥 Create Invoice with the values from the frontend
            invoice = Invoice.objects.create(
                customer=customer,
                custom_details=custom_details if not customer else {},
                add_as_customer=add_as_customer,
                date=payload.get("date"),
                due_date=payload.get("due_date"),
                status=payload.get("status", "draft"),
                items=items,
                # Use the values calculated in the frontend
                subtotal=payload.get("subtotal", 0),
                vat=payload.get("vat", 0),
                total=payload.get("total", 0),
                extra_data=payload.get("extra_data", {}),
                notes=payload.get("notes", []),
                created_by=request.user
            )
            
            # 🔥 PRINT WHAT WAS SAVED
            print("\n" + "="*50)
            print("SAVED TO DATABASE:")
            print("="*50)
            print(f"Invoice ID: {invoice.id}")
            print(f"Status: {invoice.status}")
            print(f"Subtotal: {invoice.subtotal}")
            print(f"VAT: {invoice.vat}")
            print(f"Total: {invoice.total}")
            print("="*50 + "\n")

            # ==========================================
            # 🔥 CREATE JOURNAL ENTRY ONLY IF STATUS IS "Posted"
            # ==========================================
            
            journal = None
            if invoice.status.lower() == "posted":
                # Fetch Accounts properly
                receivable_account = get_object_or_404(Account, code="1100")
                revenue_account = get_object_or_404(Account, code="4000")
                vat_account = get_object_or_404(Account, code="2200")

                entries = []

                # DR Accounts Receivable (Full Invoice Total)
                entries.append({
                    "account": receivable_account.id,
                    "debit": float(invoice.total),
                    "credit": 0
                })

                # CR Sales Revenue (Subtotal)
                entries.append({
                    "account": revenue_account.id,
                    "debit": 0,
                    "credit": float(invoice.subtotal)
                })

                # CR VAT Payable ONLY IF there is VAT
                if invoice.vat > 0:
                    entries.append({
                        "account": vat_account.id,
                        "debit": 0,
                        "credit": float(invoice.vat)
                    })

                # Only create journal if we have entries
                if entries:
                    journal = ManualJournal.objects.create(
                        date=invoice.date,
                        currency="AED",
                        status="posted",
                        notes=f"Sales Invoice - {invoice.number}",
                        entries=entries,
                        created_by=request.user
                    )

                    if not journal.is_balanced:
                        raise Exception("Journal not balanced")

                    # Store journal entries in invoice
                    invoice.journal_entries = entries
                    invoice.save()
                    
                    print("\n" + "="*50)
                    print("JOURNAL CREATED:")
                    print("="*50)
                    print(f"Journal ID: {journal.id}")
                    print(f"Entries: {entries}")
                    print("="*50 + "\n")

            return Response({
                "success": True,
                "invoice_id": invoice.id,
                "journal_id": journal.id if journal else None,
                "number": invoice.number,
                "status": invoice.status,
                "subtotal": invoice.subtotal,
                "vat": invoice.vat,
                "total": invoice.total
            }, status=201)

        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}\n")
            return Response({"error": str(e)}, status=400)



class InvoicePostView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        invoice = get_object_or_404(Invoice, pk=pk)

        if invoice.status.lower() != "draft":
            return Response(
                {"error": "Only draft invoices can be posted"},
                status=400
            )

        receivable_account = get_object_or_404(Account, code="1100")
        revenue_account = get_object_or_404(Account, code="4000")
        vat_account = get_object_or_404(Account, code="2200")

        entries = [
            {
                "account": receivable_account.id,
                "debit": float(invoice.total),
                "credit": 0
            },
            {
                "account": revenue_account.id,
                "debit": 0,
                "credit": float(invoice.subtotal)
            }
        ]

        if invoice.vat > 0:
            entries.append({
                "account": vat_account.id,
                "debit": 0,
                "credit": float(invoice.vat)
            })

        journal = ManualJournal.objects.create(
            date=invoice.date,
            currency="AED",
            status="Posted",
            notes=f"Sales Invoice - {invoice.number}",
            entries=entries,
            created_by=request.user
        )

        if not journal.is_balanced:
            raise Exception("Journal not balanced")

        invoice.status = "posted"
        invoice.journal_entries = entries
        invoice.save()

        return Response({
            "success": True,
            "journal_id": journal.id
        })


class InvoiceMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        invoice = get_object_or_404(Invoice, pk=pk)
        print(f"Marking invoice {pk} as paid. Current status: {invoice.status}")

        if invoice.status.lower() not in ["posted", "overdue"]:
            return Response(
                {"error": "Only posted or overdue invoices can be marked as paid"},
                status=400
            )

        payment_account_id = request.data.get("payment_account")
        print(f"Payment account ID: {payment_account_id}")

        if not payment_account_id:
            return Response(
                {"error": "Payment account required"},
                status=400
            )

        payment_account = get_object_or_404(Account, id=payment_account_id)
        receivable_account = get_object_or_404(Account, code="1100")
        
        print(f"Payment account: {payment_account.name} ({payment_account.code})")
        print(f"Receivable account: {receivable_account.name} ({receivable_account.code})")
        print(f"Invoice total: {invoice.total}")

        entries = [
            {
                "account": payment_account.id,
                "debit": float(invoice.total),
                "credit": 0
            },
            {
                "account": receivable_account.id,
                "debit": 0,
                "credit": float(invoice.total)
            }
        ]
        
        print(f"Entries: {entries}")

        # Try to create journal and catch any errors
        try:
            journal = ManualJournal.objects.create(
                date=invoice.date,
                currency="AED",
                status="paid",  # Changed from "posted" to "paid"
                notes=f"Payment for Invoice - {invoice.number}",
                entries=entries,
                created_by=request.user
            )
            print(f"Journal created with ID: {journal.id}")
        except Exception as e:
            print(f"Error creating journal: {str(e)}")
            return Response(
                {"error": f"Failed to create journal: {str(e)}"},
                status=500
            )

        invoice.status = "paid"
        invoice.save()
        print(f"Invoice status updated to: {invoice.status}")

        return Response({
            "success": True,
            "journal_id": journal.id
        })



class InvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema().get("invoices", {})
        columns = schema.get("table_columns", [])

        invoices = Invoice.objects.select_related("customer")

        data = []

        for invoice in invoices:
            row = {"id": invoice.id}

            for col in columns:
                if hasattr(invoice, col):
                    row[col] = getattr(invoice, col)
                elif col == "customer_name" and invoice.customer:
                    row[col] = invoice.customer.company
                else:
                    row[col] = invoice.extra_data.get(col)

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })


class InvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)

        data = {
            "id": invoice.id,
            "number": invoice.number,
            "customer": invoice.customer.id if invoice.customer else None,
            "customer_name": invoice.customer.company if invoice.customer else None,
            "custom_details": invoice.custom_details,
            "date": invoice.date,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "items": invoice.items,
            "subtotal": invoice.subtotal,
            "vat": invoice.vat,
            "total": invoice.total,
            "extra_data": invoice.extra_data,
            "notes": invoice.notes,
            "created_at": invoice.created_at,
            "updated_at": invoice.updated_at,
            "created_by": invoice.created_by.username if invoice.created_by else None,
        }

        return Response({
            "success": True,
            "invoice": data
        })
    


class InvoiceUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)

        payload = request.data

        invoice.date = payload.get("date", invoice.date)
        invoice.due_date = payload.get("due_date", invoice.due_date)
        invoice.status = payload.get("status", invoice.status)
        invoice.items = payload.get("items", invoice.items)
        invoice.extra_data = payload.get("extra_data", invoice.extra_data)

        invoice.save()  # 🔥 totals recalculated automatically

        return Response({
            "success": True,
            "message": "Invoice updated"
        })



import base64
from io import BytesIO
from reportlab.platypus import (SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from io import BytesIO

class InvoicePDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        company = CompanyProfile.objects.first()
        
        # Prepare customer data
        if invoice.customer:
            customer = {
                "company": invoice.customer.company,
                "contact_name": invoice.customer.contact_name,
                "email": invoice.customer.email,
                "address": invoice.customer.extra_data.get("address", "")
            }
        else:
            customer = {
                "company": invoice.custom_details.get("companyName", ""),
                "contact_name": invoice.custom_details.get("contactPerson", ""),
                "email": invoice.custom_details.get("email", ""),
                "address": invoice.custom_details.get("address", "")
            }
        
        # Prepare items
        items = []
        for item in invoice.items:
            items.append({
                "description": item.get("description", ""),
                "quantity": item.get("quantity", 0),
                "price": f"{Decimal(str(item.get('price', 0))):,.2f}",
                "amount": f"{Decimal(str(item.get('amount', 0))):,.2f}"
            })
        
        # Prepare context
        context = {
            "company": company,
            "invoice": {
                "number": invoice.number,
                "date": invoice.date.strftime("%d %b %Y"),
                "due_date": invoice.due_date.strftime("%d %b %Y") if invoice.due_date else "N/A",
                "status": invoice.status,
            },
            "customer": customer,
            "items": items,
            "subtotal": f"{invoice.subtotal:,.2f}",
            "vat": f"{invoice.vat:,.2f}",
            "total": f"{invoice.total:,.2f}",
            "generation_date": timezone.now().strftime("%d %b %Y, %I:%M %p"),
        }
        
        # Render HTML
        template = get_template("pdf/invoice.html")
        html = template.render(context)
        
        # Create PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
        
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename=Invoice-{invoice.number}.pdf'
            return response
        
        return HttpResponse("Error generating PDF", status=500)


class InvoiceDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        invoice.delete()

        return Response({
            "success": True,
            "message": "Invoice deleted"
        })


class InvoiceAddNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)

        text = request.data.get("text")
        if not text:
            return Response(
                {"error": "Note text required"},
                status=400
            )

        note = {
            "id": str(uuid.uuid4()),
            "text": text,
            "created_by": request.user.id,
            "user_name": request.user.username,
            "created_at": timezone.now().isoformat()
        }

        notes = invoice.notes or []
        notes.append(note)

        invoice.notes = notes
        invoice.save()

        return Response({
            "success": True,
            "note": note
        }, status=201)


class InvoiceDeleteNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, note_id):
        invoice = get_object_or_404(Invoice, pk=pk)

        notes = invoice.notes or []
        updated_notes = [n for n in notes if str(n.get("id")) != str(note_id)]

        if len(notes) == len(updated_notes):
            return Response(
                {"error": "Note not found"},
                status=404
            )

        invoice.notes = updated_notes
        invoice.save()

        return Response({
            "success": True,
            "message": "Note deleted"
        })


from django.db.models import Sum
from decimal import Decimal, ROUND_HALF_UP


class OriginalInvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        invoices = Invoice.objects.filter(
            document_type="INVOICE"
        )

        data = [
            {
                "id": inv.id,
                "number": inv.number,
                "total": inv.total,
                "customer_name": inv.customer.company if inv.customer else None
            }
            for inv in invoices
        ]

        return Response({
            "success": True,
            "rows": data
        })



class InvoiceAdjustmentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        data = request.data

        invoice_id = data.get("invoice_id")
        document_type = data.get("document_type")
        items = data.get("items", [])
        date = data.get("date")

        # ================= BASIC VALIDATION =================

        if document_type not in ["CREDIT_NOTE", "DEBIT_NOTE"]:
            return Response({"error": "Invalid document type"}, status=400)

        if not invoice_id:
            return Response({"error": "Invoice required"}, status=400)

        if not items:
            return Response({"error": "At least one item required"}, status=400)

        # ================= GET ORIGINAL INVOICE =================

        original_invoice = get_object_or_404(Invoice, id=invoice_id)

        if original_invoice.document_type in ["CREDIT_NOTE", "DEBIT_NOTE"]:
            return Response(
                {"error": "Cannot adjust a credit/debit note"},
                status=400
            )

        # ================= CALCULATE TOTALS =================

        subtotal = Decimal("0.00")
        vat_total = Decimal("0.00")
        inventory_items = []

        for item in items:

            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            vat_included = item.get("vat_included", False)

            if qty <= 0 or price <= 0:
                return Response(
                    {"error": "Invalid quantity or price"},
                    status=400
                )

            line_total = qty * price
            subtotal += line_total

            if vat_included:
                vat_total += line_total * Decimal("0.05")

            if item.get("type") == "inventory" and item.get("inventory_id"):
                inventory_items.append({
                    "id": item["inventory_id"],
                    "quantity": qty,
                    "price": price,
                    "line_total": line_total
                })

        vat_total = vat_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + vat_total

        # ================= CREDIT LIMIT CHECK =================

        if document_type == "CREDIT_NOTE":

            previous_credits = Invoice.objects.filter(
                related_invoice=original_invoice,
                document_type="CREDIT_NOTE"
            ).aggregate(
                total_sum=Sum("total")
            )["total_sum"] or Decimal("0.00")

            remaining = original_invoice.total - previous_credits

            if total > remaining:
                return Response(
                    {"error": "Credit exceeds remaining invoice balance"},
                    status=400
                )

        # ================= CREATE ADJUSTMENT =================

        adjustment = Invoice.objects.create(
            customer=original_invoice.customer,
            custom_details=original_invoice.custom_details,
            document_type=document_type,
            related_invoice=original_invoice,
            date=date,
            status="posted",
            items=items,
            subtotal=subtotal,
            vat=vat_total,
            total=total,
            created_by=request.user
        )

        # ================= UPDATE INVENTORY =================

        if document_type == "CREDIT_NOTE" and inventory_items:

            for inv_item in inventory_items:
                try:
                    inventory = InventoryItem.objects.get(id=inv_item["id"])

                    inventory.current_quantity += inv_item["quantity"]
                    inventory.save()

                except InventoryItem.DoesNotExist:
                    print(f"Inventory item {inv_item['id']} not found")

        # ================= JOURNAL ENTRIES =================

        revenue = get_object_or_404(Account, code="4000")
        output_vat = get_object_or_404(Account, code="2200")
        receivable = get_object_or_404(Account, code="1100")

        inventory_account = get_object_or_404(Account, code="1800")
        cogs_account = get_object_or_404(Account, code="5000")

        expense = get_object_or_404(Account, code="5040")
        input_vat = get_object_or_404(Account, code="2100")
        payable = get_object_or_404(Account, code="2010")

        entries = []

        # ================= CREDIT NOTE =================

        if document_type == "CREDIT_NOTE":

            # Reverse sales revenue
            entries.append({
                "account": revenue.id,
                "debit": float(subtotal),
                "credit": 0
            })

            # Reverse VAT
            if vat_total > 0:
                entries.append({
                    "account": output_vat.id,
                    "debit": float(vat_total),
                    "credit": 0
                })

            # Reduce receivable
            entries.append({
                "account": receivable.id,
                "debit": 0,
                "credit": float(total)
            })

            # Handle inventory returns
            for inv_item in inventory_items:

                try:
                    inventory = InventoryItem.objects.get(id=inv_item["id"])

                    cogs_amount = inv_item["quantity"] * inventory.cost_price

                    # DR Inventory
                    entries.append({
                        "account": inventory_account.id,
                        "debit": float(cogs_amount),
                        "credit": 0
                    })

                    # CR COGS
                    entries.append({
                        "account": cogs_account.id,
                        "debit": 0,
                        "credit": float(cogs_amount)
                    })

                except InventoryItem.DoesNotExist:

                    fallback = inv_item["line_total"]

                    entries.append({
                        "account": inventory_account.id,
                        "debit": float(fallback),
                        "credit": 0
                    })

                    entries.append({
                        "account": cogs_account.id,
                        "debit": 0,
                        "credit": float(fallback)
                    })

        # ================= DEBIT NOTE =================

        else:

            entries.append({
                "account": expense.id,
                "debit": 0,
                "credit": float(subtotal)
            })

            if vat_total > 0:
                entries.append({
                    "account": input_vat.id,
                    "debit": 0,
                    "credit": float(vat_total)
                })

            entries.append({
                "account": payable.id,
                "debit": float(total),
                "credit": 0
            })

        # ================= VERIFY BALANCE =================

        total_debit = sum(e["debit"] for e in entries)
        total_credit = sum(e["credit"] for e in entries)

        if round(total_debit, 2) != round(total_credit, 2):
            raise Exception(
                f"Journal not balanced: Debits {total_debit} != Credits {total_credit}"
            )

        # ================= CREATE JOURNAL =================

        journal = ManualJournal.objects.create(
            date=date,
            currency="AED",
            status="Posted",
            notes=f"{document_type} - {adjustment.number}",
            entries=entries,
            created_by=request.user
        )

        return Response({
            "success": True,
            "id": adjustment.id,
            "number": adjustment.number,
            "total": adjustment.total,
            "inventory_updated": len(inventory_items) if document_type == "CREDIT_NOTE" else 0
        }, status=201)




class InvoiceAdjustmentMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, adjustment_id):

        payment_account_id = request.data.get("payment_account")

        if not payment_account_id:
            return Response({"error": "Payment account required"}, status=400)

        payment_account = get_object_or_404(Account, id=payment_account_id)

        # Optional: Validate that it's a cash/bank account
        if payment_account.code not in ["1010", "1020"]:
            return Response(
                {"error": "Payment account must be Cash (1010) or Bank (1020)"},
                status=400
            )

        adjustment = get_object_or_404(
            Invoice,
            id=adjustment_id,
            document_type__in=["CREDIT_NOTE", "DEBIT_NOTE"]
        )

        if adjustment.status.lower() == "paid":
            return Response({"error": "Already paid"}, status=400)

        amount = adjustment.total

        # Accounts
        receivable = get_object_or_404(Account, code="1100")
        payable = get_object_or_404(Account, code="2010")

        entries = []

        if adjustment.document_type == "CREDIT_NOTE":
            # Refund customer
            entries.append({
                "account": receivable.id,
                "debit": float(amount),
                "credit": 0
            })
            entries.append({
                "account": payment_account.id,
                "debit": 0,
                "credit": float(amount)
            })

        else:  # DEBIT_NOTE
            # Pay supplier
            entries.append({
                "account": payable.id,
                "debit": float(amount),
                "credit": 0
            })
            entries.append({
                "account": payment_account.id,
                "debit": 0,
                "credit": float(amount)
            })

        journal = ManualJournal.objects.create(
            date=adjustment.date,
            currency="AED",
            status="Posted",
            notes=f"Payment - {adjustment.number}",
            entries=entries,
            created_by=request.user
        )

        if not journal.is_balanced:
            raise Exception("Journal not balanced")

        # Mark paid
        adjustment.status = "paid"
        adjustment.save()

        # ================= INVENTORY UPDATE =================
        for item in adjustment.items:
            product_id = item.get("product_id")
            qty = Decimal(str(item.get("quantity", 0)))

            if product_id:
                product = Product.objects.filter(id=product_id).first()
                if product:
                    if adjustment.document_type == "CREDIT_NOTE":
                        product.stock += qty   # Returned from customer
                    else:
                        product.stock -= qty   # Returned to supplier
                    product.save()

        return Response({
            "success": True,
            "message": "Adjustment marked as paid",
            "journal_id": journal.id
        })


        
class InvoiceAdjustmentListPageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        adjustments = Invoice.objects.filter(
            document_type__in=["CREDIT_NOTE", "DEBIT_NOTE"]
        ).select_related("customer")

        data = []

        for inv in adjustments:
            data.append({
                "id": inv.id,
                "number": inv.number,
                "document_type": inv.document_type,
                "date": inv.date,
                "total": float(inv.total),
                "status": inv.status,
                "customer_name": inv.customer.company if inv.customer else None,
            })

        return Response({
            "success": True,
            "rows": data
        })


class InvoiceAdjustmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, adjustment_id):

        adjustment = get_object_or_404(
            Invoice,
            id=adjustment_id,
            document_type__in=["CREDIT_NOTE", "DEBIT_NOTE"]
        )

        original_invoice = adjustment.related_invoice

        # ================= CORRECT TOTAL CALCULATION =================

        subtotal = Decimal("0.00")
        vat_total = Decimal("0.00")

        for item in adjustment.items or []:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            vat_included = item.get("vat_included", False)

            line_total = qty * price
            subtotal += line_total

            if vat_included:
                vat_total += line_total * Decimal("0.05")

        vat_total = vat_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + vat_total

        # ================= REMAINING BALANCE =================

        remaining_balance = None

        if adjustment.document_type == "CREDIT_NOTE" and original_invoice:

            previous_credits = Invoice.objects.filter(
                related_invoice=original_invoice,
                document_type="CREDIT_NOTE"
            ).exclude(id=adjustment.id).aggregate(
                total_sum=Sum("total")
            )["total_sum"] or Decimal("0.00")

            remaining_balance = (
                original_invoice.total - previous_credits - total
            )

        # ================= RESPONSE =================

        data = {
            "id": adjustment.id,
            "number": adjustment.number,
            "document_type": adjustment.document_type,
            "date": adjustment.date,
            "due_date": adjustment.due_date,
            "status": adjustment.status,

            "customer": {
                "id": adjustment.customer.id if adjustment.customer else None,
                "name": adjustment.customer.company if adjustment.customer else None,
            },

            "original_invoice": {
                "id": original_invoice.id if original_invoice else None,
                "number": original_invoice.number if original_invoice else None,
                "total": float(original_invoice.total) if original_invoice else None,
            },

            "items": adjustment.items,

            "subtotal": float(subtotal),
            "vat": float(vat_total),
            "total": float(total),

            "remaining_balance": (
                float(remaining_balance)
                if remaining_balance is not None
                else None
            ),

            "created_at": adjustment.created_at,
            "updated_at": adjustment.updated_at,
        }

        return Response({
            "success": True,
            "adjustment": data
        })

class InvoiceAdjustmentPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        adjustment = get_object_or_404(
            Invoice,
            pk=pk,
            document_type__in=["CREDIT_NOTE", "DEBIT_NOTE"]
        )

        company = CompanyProfile.objects.first()
        original_invoice = adjustment.related_invoice

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename={adjustment.document_type}-{adjustment.number}.pdf'
        )

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # ================= HEADER =================

        title_text = "CREDIT NOTE" if adjustment.document_type == "CREDIT_NOTE" else "DEBIT NOTE"

        elements.append(Paragraph(f"<b>{title_text}</b>", styles["Title"]))
        elements.append(Spacer(1, 0.3 * inch))

        # ================= COMPANY INFO =================

        if company:
            company_info = f"""
            <b>{company.company_name}</b><br/>
            {company.company_address}<br/>
            {company.city or ''} {company.state or ''}<br/>
            {company.country}<br/>
            VAT: {company.vat_number if company.is_vat_registered else "Not Registered"}
            """

            elements.append(Paragraph(company_info, styles["Normal"]))
            elements.append(Spacer(1, 0.4 * inch))

        # ================= ADJUSTMENT INFO =================

        info_text = f"""
        <b>Number:</b> {adjustment.number}<br/>
        <b>Date:</b> {adjustment.date}<br/>
        <b>Status:</b> {adjustment.status.upper()}
        """

        if original_invoice:
            info_text += f"<br/><b>Related Invoice:</b> {original_invoice.number}"

        elements.append(Paragraph(info_text, styles["Normal"]))
        elements.append(Spacer(1, 0.4 * inch))

        # ================= CUSTOMER =================

        customer_name = adjustment.customer.company if adjustment.customer else ""
        elements.append(Paragraph(f"<b>Customer:</b> {customer_name}", styles["Heading3"]))
        elements.append(Spacer(1, 0.3 * inch))

        # ================= ITEMS TABLE =================

        data = [["Description", "Qty", "Price", "Amount"]]

        subtotal = Decimal("0.00")

        for item in adjustment.items:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            amount = qty * price
            subtotal += amount

            data.append([
                item.get("description"),
                str(qty),
                f"{price:,.2f}",
                f"{amount:,.2f}",
            ])

        vat = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        total = subtotal + vat

        data.append(["", "", "Subtotal", f"{subtotal:,.2f}"])
        data.append(["", "", "VAT (5%)", f"{vat:,.2f}"])
        data.append(["", "", "Total", f"{total:,.2f}"])

        table = Table(data, colWidths=[2.5*inch, 0.8*inch, 1.2*inch, 1.2*inch])

        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.5 * inch))

        # ================= REMAINING BALANCE =================

        if adjustment.document_type == "CREDIT_NOTE" and original_invoice:

            previous_credits = Invoice.objects.filter(
                related_invoice=original_invoice,
                document_type="CREDIT_NOTE"
            ).exclude(id=adjustment.id).aggregate(
                total_sum=Sum("total")
            )["total_sum"] or Decimal("0.00")

            remaining_balance = (
                original_invoice.total - previous_credits - total
            )

            elements.append(
                Paragraph(
                    f"<b>Remaining Invoice Balance:</b> {remaining_balance:,.2f}",
                    styles["Normal"]
                )
            )

        doc.build(elements)

        return response
    

    

class ManualJournalSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("manual_journals", {})
        return Response({
            "success": True,
            "schema": schema
        })




class ManualJournalCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data

        entries = payload.get("entries", [])

        if not entries:
            return Response(
                {"error": "At least one journal entry required"},
                status=400
            )

        journal = ManualJournal.objects.create(
            date=payload.get("date"),
            currency=payload.get("currency", "USD"),
            status=payload.get("status", "Draft"),
            notes=payload.get("notes"),
            entries=entries,
            created_by=request.user
        )

        if not journal.is_balanced:
            return Response(
                {"error": "Debits must equal credits"},
                status=400
            )

        return Response({
            "success": True,
            "journal_id": journal.id,
            "journal_number": journal.journal_number
        }, status=201)


class ManualJournalListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema().get("manual_journals", {})
        columns = schema.get("table_columns", [])

        journals = ManualJournal.objects.all()

        data = []

        for journal in journals:
            row = {"id": journal.id}

            for col in columns:
                if hasattr(journal, col):
                    row[col] = getattr(journal, col)

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })


class ManualJournalDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        journal = get_object_or_404(ManualJournal, pk=pk)

        enriched_entries = []

        for entry in journal.entries:

            account_id = entry.get("account")

            account = None
            if account_id:
                account = Account.objects.filter(id=account_id).first()

            enriched_entries.append({
                "account_id": account_id,
                "account_code": account.code if account else None,
                "account_name": account.name if account else None,
                "account_display": (
                    f"{account.code} - {account.name}"
                    if account else str(account_id)
                ),
                "debit": entry.get("debit", 0),
                "credit": entry.get("credit", 0),
            })

        return Response({
            "success": True,
            "journal": {
                "id": journal.id,
                "journal_number": journal.journal_number,
                "date": journal.date,
                "currency": journal.currency,
                "status": journal.status,
                "notes": journal.notes,
                "entries": enriched_entries,
                "total_debits": journal.total_debits,
                "total_credits": journal.total_credits,
                "difference": journal.difference,
                "is_balanced": journal.is_balanced
            }
        })


class ManualJournalUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        journal = get_object_or_404(ManualJournal, pk=pk)

        # 🔒 Prevent editing posted journal
        if journal.status == "Posted":
            return Response(
                {"error": "Posted journals cannot be edited"},
                status=400
            )

        payload = request.data

        journal.date = payload.get("date", journal.date)
        journal.currency = payload.get("currency", journal.currency)
        journal.status = payload.get("status", journal.status)
        journal.notes = payload.get("notes", journal.notes)
        journal.entries = payload.get("entries", journal.entries)

        journal.save()  # 🔥 totals recalculated automatically

        if not journal.is_balanced:
            return Response(
                {"error": "Debits must equal credits"},
                status=400
            )

        return Response({
            "success": True,
            "message": "Journal updated"
        })




class ManualJournalDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        journal = get_object_or_404(ManualJournal, pk=pk)

        # 🔥 Recommended safety
        # if journal.status == "Posted":
        #     return Response(
        #         {"error": "Posted journals cannot be deleted"},
        #         status=400
        #     )

        journal.delete()

        return Response({
            "success": True,
            "message": "Journal deleted"
        })



class ExpenseInvoiceSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("expense_invoices", {})
        return Response({
            "success": True,
            "schema": schema
        })



from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone


class ExpenseInvoiceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        try:
            data = request.data

            if not data.get("invoice_number"):
                return Response({"error": "Invoice number required"}, status=400)

            if not data.get("vendor"):
                return Response({"error": "Vendor required"}, status=400)

            if not data.get("debit_account"):
                return Response({"error": "Debit account required"}, status=400)

            items = data.get("items", [])
            if not items:
                return Response({"error": "At least one item required"}, status=400)

            vendor = get_object_or_404(Vendor, id=data.get("vendor"))
            debit_account = get_object_or_404(Account, id=data.get("debit_account"))

            subtotal = Decimal("0.00")
            total_vat = Decimal("0.00")
            grand_total = Decimal("0.00")

            calculated_items = []

            for item in items:
                qty = Decimal(str(item.get("quantity", 0)))
                price = Decimal(str(item.get("unit_price", 0)))

                if qty <= 0:
                    return Response({"error": "Invalid quantity"}, status=400)

                base = qty * price
                vat = Decimal("0.00")

                if item.get("vat_enabled", True):
                    if item.get("vat_included", False):
                        vat = (base * Decimal("5") / Decimal("105")).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                        base -= vat
                    else:
                        vat = (base * Decimal("0.05")).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )

                total = base + vat

                subtotal += base
                total_vat += vat
                grand_total += total

                calculated_items.append({
                    "product_name": item.get("product_name"),
                    "quantity": float(qty),
                    "unit_price": float(price),
                    "line_amount": float(base),
                    "vat_amount": float(vat),
                    "total": float(total)
                })

            # Always POSTED
            invoice = ExpenseInvoice.objects.create(
                invoice_number=data.get("invoice_number"),
                vendor=vendor,
                vendor_name=vendor.company,
                date=data.get("date"),
                due_date=data.get("due_date"),
                amount=subtotal,
                vat_amount=total_vat,
                total_amount=grand_total,
                status="Posted",
                invoice_type=data.get("invoice_type"),
                items=calculated_items,
                created_by=request.user
            )

            accounts_payable = Account.objects.get(id=12)  # fixed AP

            entries = [
                {
                    "account": debit_account.id,
                    "debit": float(invoice.amount),
                    "credit": 0
                }
            ]

            if invoice.vat_amount > 0:
                vat_account = get_object_or_404(Account, code="2100")
                if vat_account:
                    entries.append({
                        "account": vat_account.id,
                        "debit": float(invoice.vat_amount),
                        "credit": 0
                    })

            entries.append({
                "account": accounts_payable.id,
                "debit": 0,
                "credit": float(invoice.total_amount)
            })

            journal = ManualJournal.objects.create(
                date=invoice.date,
                currency="AED",
                status="Posted",
                notes=f"Vendor Invoice - {invoice.invoice_number}",
                entries=entries,
                created_by=request.user
            )

            if not journal.is_balanced:
                raise Exception("Journal not balanced")

            invoice.journal_entries = entries
            invoice.save()

            return Response({
                "success": True,
                "invoice_id": invoice.id,
                "journal_id": journal.id
            }, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=400)







class ExpenseInvoiceMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        try:
            invoice = get_object_or_404(ExpenseInvoice, pk=pk)

            # =============================
            # VALIDATION
            # =============================

            if invoice.status != "Posted":
                return Response({
                    "error": "Only posted invoices can be paid"
                }, status=400)

            if invoice.status == "Paid":
                return Response({
                    "error": "Invoice already paid"
                }, status=400)

            bank_account_id = request.data.get("bank_account")

            if bank_account_id in [None, "", 0]:
                return Response({
                    "error": "Bank account required"
                }, status=400)

            # Fetch bank account (must be Asset)
            bank_account = get_object_or_404(
                Account,
                id=bank_account_id,
                type="Asset"
            )

            # Fixed Accounts Payable (id = 12)
            accounts_payable = get_object_or_404(
                Account,
                id=12,
                type="Liability"
            )

            # =============================
            # CREATE PAYMENT JOURNAL
            # =============================

            entries = [
                {
                    "account": accounts_payable.id,
                    "debit": float(invoice.total_amount),
                    "credit": 0
                },
                {
                    "account": bank_account.id,
                    "debit": 0,
                    "credit": float(invoice.total_amount)
                }
            ]

            journal = ManualJournal.objects.create(
                date=timezone.now().date(),
                currency="AED",
                status="Posted",
                notes=f"Payment - Invoice {invoice.invoice_number}",
                entries=entries,
                created_by=request.user
            )

            if not journal.is_balanced:
                raise Exception("Payment journal not balanced")

            # =============================
            # UPDATE INVOICE STATUS
            # =============================

            invoice.status = "Paid"
            invoice.save()

            return Response({
                "success": True,
                "journal_id": journal.id
            })

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=400)





class ExpenseInvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("expense_invoices", {})
        columns = schema.get("table_columns", [])

        invoices = ExpenseInvoice.objects.all()

        rows = []

        for inv in invoices:
            row = {"id": inv.id}

            for col in columns:
                if hasattr(inv, col):
                    row[col] = getattr(inv, col)
                else:
                    row[col] = inv.extra_data.get(col)

            rows.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": rows
        })





class ExpenseInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(ExpenseInvoice, pk=pk)

        return Response({
            "success": True,
            "invoice": {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "vendor": {
    "id": invoice.vendor.id if invoice.vendor else None,
    "company": invoice.vendor.company if invoice.vendor else invoice.vendor_name,
    "email": invoice.vendor.email if invoice.vendor else None,
    "phone": invoice.vendor.phone if invoice.vendor else None,
},

                "date": invoice.date,
                "due_date": invoice.due_date,
                "amount": invoice.amount,
                "vat_amount": invoice.vat_amount,
                "total_amount": invoice.total_amount,
                "status": invoice.status,
                "items": invoice.items,
                "journal_entries": invoice.journal_entries,
                "pdf_file": invoice.pdf_file,
                "total_debits": invoice.total_debits,
                "total_credits": invoice.total_credits,
                "is_balanced": invoice.is_balanced
            }
        })


class ExpenseInvoiceUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        invoice = get_object_or_404(ExpenseInvoice, pk=pk)

        for key, value in request.data.items():
            if hasattr(invoice, key):
                setattr(invoice, key, value)

        invoice.save()

        return Response({"success": True})


class ExpenseInvoiceDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        invoice = get_object_or_404(ExpenseInvoice, pk=pk)
        invoice.delete()

        return Response({"success": True})



class ExpenseInvoiceMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        try:
            invoice = get_object_or_404(ExpenseInvoice, pk=pk)

            # =============================
            # VALIDATION
            # =============================

            if invoice.status == "Paid":
                return Response({
                    "error": "Invoice already paid"
                }, status=400)

            if invoice.status != "Posted":
                return Response({
                    "error": "Only posted invoices can be paid"
                }, status=400)

            bank_account_id = request.data.get("bank_account")

            if bank_account_id in [None, "", 0]:
                return Response({
                    "error": "Bank account required"
                }, status=400)

            bank_account = get_object_or_404(
                Account,
                id=bank_account_id,
                type="Asset"
            )

            accounts_payable = get_object_or_404(
                Account,
                id=12,
                type="Liability"
            )

            from decimal import Decimal
            amount = Decimal(str(invoice.total_amount))

            entries = [
                {
                    "account": accounts_payable.id,
                    "debit": str(amount),
                    "credit": "0.00"
                },
                {
                    "account": bank_account.id,
                    "debit": "0.00",
                    "credit": str(amount)
                }
            ]

            journal = ManualJournal.objects.create(
                date=timezone.now().date(),
                currency="AED",
                status="Posted",
                notes=f"Payment - Invoice {invoice.invoice_number}",
                entries=entries,
                created_by=request.user
            )

            if not journal.is_balanced:
                raise Exception(
                    f"Payment journal not balanced. Difference: {journal.difference}"
                )

            invoice.status = "Paid"
            invoice.save()

            return Response({
                "success": True,
                "journal_id": journal.id
            })

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=400)



class CompanyProfileSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("company_profile", {})

        return Response({
            "success": True,
            "schema": schema
        })
    
class CompanyProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = CompanyProfile.objects.first()

        if not profile:
            return Response({
                "success": True,
                "profile": None
            })

        return Response({
            "success": True,
            "profile": {
                "id": profile.id,
                "company_name": profile.company_name,
                "company_logo": profile.company_logo,
                "company_address": profile.company_address,
                "city": profile.city,
                "state": profile.state,
                "country": profile.country,
                "postal_code": profile.postal_code,
                "phone_number": profile.phone_number,
                "email": profile.email,
                "website": profile.website,
                "is_vat_registered": profile.is_vat_registered,
                "vat_number": profile.vat_number,
                "corporate_registration_number": profile.corporate_registration_number,
                "signature_image": profile.signature_image,
                "company_stamp": profile.company_stamp,
                "custom_footer_notes": profile.custom_footer_notes,
            }
        })
    

class CompanyProfileSaveView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data

        profile = CompanyProfile.objects.first()

        if profile:
            # UPDATE
            for key, value in data.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)

            profile.save()

        else:
            # CREATE
            profile = CompanyProfile.objects.create(
                **data,
                created_by=request.user
            )

        return Response({
            "success": True,
            "profile_id": profile.id
        })

class CompanyProfileDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        profile = CompanyProfile.objects.first()

        if profile:
            profile.delete()

        return Response({"success": True})







class InventoryInvoiceSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = request.tenant.get_schema().get("inventory_invoices", {})
        return Response({
            "success": True,
            "schema": schema
        })


class InventoryInvoiceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        try:
            payload = request.data
            items = payload.get("items", [])
            vendor_id = payload.get("vendor")
            status = payload.get("status", "draft")

            if status not in ["draft", "posted"]:
                return Response(
                    {"error": "Invalid status"},
                    status=400
                )

            if not vendor_id:
                return Response({"error": "Vendor is required"}, status=400)

            vendor = get_object_or_404(Vendor, id=vendor_id)

            if not items:
                return Response({"error": "At least one item required"}, status=400)

            validated_items = []
            subtotal = Decimal("0.00")
            total_vat = Decimal("0.00")

            for item in items:

                inventory_id = item.get("inventory_item")
                if not inventory_id:
                    return Response({"error": "Inventory item required"}, status=400)

                inventory_item = get_object_or_404(
                    InventoryItem,
                    id=inventory_id
                )

                qty = Decimal(str(item.get("quantity", 0)))
                price = Decimal(str(item.get("price", 0)))

                if qty <= 0:
                    return Response({"error": "Quantity must be greater than 0"}, status=400)

                if price < 0:
                    return Response({"error": "Price cannot be negative"}, status=400)

                vat_applicable = bool(item.get("vat_applicable", False))

                line_amount = qty * price
                vat_amount = Decimal("0.00")

                if vat_applicable:
                    vat_amount = (line_amount * Decimal("0.05")).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP
                    )

                subtotal += line_amount
                total_vat += vat_amount

                validated_items.append({
                    "inventory_item": inventory_id,
                    "quantity": float(qty),
                    "price": float(price),
                    "vat_applicable": vat_applicable,
                    "line_amount": float(line_amount),
                    "vat_amount": float(vat_amount),
                })

            total = subtotal + total_vat

            # ==============================
            # CREATE INVOICE
            # ==============================

            invoice = InventoryInvoice.objects.create(
                vendor=vendor,
                date=payload.get("date"),
                due_date=payload.get("due_date"),
                status=status,
                items=validated_items,
                subtotal=subtotal,
                vat=total_vat,
                total=total,
                notes=payload.get("notes", []),
                created_by=request.user
            )

            # ==========================================
            # IF POSTED → UPDATE STOCK + JOURNAL
            # ==========================================

            if status == "posted":

                # 🔹 Update stock (weighted average)
                for item in validated_items:

                    inventory_item = InventoryItem.objects.select_for_update().get(
                        id=item["inventory_item"]
                    )

                    qty = Decimal(str(item["quantity"]))
                    price = Decimal(str(item["price"]))

                    old_qty = inventory_item.current_quantity
                    old_cost = inventory_item.cost_price

                    total_old = old_qty * old_cost
                    total_new = qty * price
                    new_qty = old_qty + qty

                    if new_qty > 0:
                        new_avg_cost = (
                            (total_old + total_new) / new_qty
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        new_avg_cost = Decimal("0.00")

                    inventory_item.current_quantity = new_qty
                    inventory_item.cost_price = new_avg_cost
                    inventory_item.save()

                    InventoryTransaction.objects.create(
                        item=inventory_item,
                        transaction_type="PURCHASE",
                        quantity=qty,
                        unit_cost=price,
                        reference=invoice.number,
                        created_by=request.user
                    )

                # 🔹 Journal Entry

                inventory_account = get_object_or_404(Account, code="1800")
                input_vat_account = Account.objects.filter(code="2100").first()
                payable_account = get_object_or_404(Account, code="2010")

                entries = []

                # DR Inventory
                entries.append({
                    "account": inventory_account.id,
                    "debit": float(subtotal),
                    "credit": 0
                })

                # DR Input VAT
                if total_vat > 0 and input_vat_account:
                    entries.append({
                        "account": input_vat_account.id,
                        "debit": float(total_vat),
                        "credit": 0
                    })

                # CR Accounts Payable
                entries.append({
                    "account": payable_account.id,
                    "debit": 0,
                    "credit": float(total)
                })

                journal = ManualJournal.objects.create(
                    date=invoice.date,
                    currency="AED",
                    status="Posted",
                    notes=f"Inventory Purchase Invoice - {invoice.number}",
                    entries=entries,
                    created_by=request.user
                )

                if not journal.is_balanced:
                    raise Exception("Journal not balanced")

            return Response({
                "success": True,
                "inventory_invoice_id": invoice.id,
                "number": invoice.number
            }, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=400)




class InventoryInvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema().get(
            "inventory_invoices", {}
        )
        columns = schema.get("table_columns", [])

        invoices = InventoryInvoice.objects.select_related("vendor")

        data = []

        for invoice in invoices:
            row = {"id": invoice.id}

            for col in columns:

                # Vendor name instead of FK id
                if col == "vendor":
                    row[col] = (
                        invoice.vendor.company
                        if invoice.vendor and hasattr(invoice.vendor, "company")
                        else None
                    )

                elif hasattr(invoice, col):
                    value = getattr(invoice, col)

                    if isinstance(value, Decimal):
                        row[col] = str(value)
                    else:
                        row[col] = value

                else:
                    row[col] = None

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })



class InventoryInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(
            InventoryInvoice.objects.select_related("vendor"),
            pk=pk
        )

        item_data = []

        for item in invoice.items:

            inventory_id = item.get("inventory_item")
            quantity = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            vat_applicable = item.get("vat_applicable", False)

            amount = (quantity * price).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            vat_amount = (
                (amount * Decimal("0.05")).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP
                )
                if vat_applicable
                else Decimal("0.00")
            )

            inventory_name = None
            item_code = None

            if inventory_id:
                try:
                    inventory = InventoryItem.objects.get(
                        id=inventory_id
                    )
                    inventory_name = inventory.item_name
                    item_code = inventory.item_code
                except InventoryItem.DoesNotExist:
                    pass

            item_data.append({
                "inventory_item": inventory_id,
                "item_code": item_code,
                "item_name": inventory_name,
                "quantity": str(quantity),
                "price": str(price),
                "vat_applicable": vat_applicable,
                "vat_amount": str(vat_amount),
                "amount": str(amount),
            })

        data = {
            "id": invoice.id,
            "number": invoice.number,
            "vendor": invoice.vendor.id if invoice.vendor else None,
            "vendor_name": (
                invoice.vendor.company
                if invoice.vendor and hasattr(invoice.vendor, "company")
                else None
            ),
            "date": invoice.date,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "items": item_data,
            "subtotal": str(invoice.subtotal),
            "vat": str(invoice.vat),
            "total": str(invoice.total),
            "notes": invoice.notes,
            "created_at": invoice.created_at,
            "created_by": (
                invoice.created_by.username
                if invoice.created_by
                else None
            ),
        }

        return Response({
            "success": True,
            "inventory_invoice": data
        })

class InventoryInvoicePostView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        invoice = get_object_or_404(InventoryInvoice, pk=pk)

        if invoice.status != "draft":
            return Response(
                {"error": "Only draft invoices can be posted"},
                status=400
            )

        subtotal = invoice.subtotal
        total_vat = invoice.vat
        total = invoice.total

        # 🔹 Update inventory
        for item in invoice.items:

            inventory_item = InventoryItem.objects.select_for_update().get(
                id=item["inventory_item"]
            )

            qty = Decimal(str(item["quantity"]))
            price = Decimal(str(item["price"]))

            old_qty = inventory_item.current_quantity
            old_cost = inventory_item.cost_price

            total_old = old_qty * old_cost
            total_new = qty * price
            new_qty = old_qty + qty

            new_avg_cost = (
                (total_old + total_new) / new_qty
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            inventory_item.current_quantity = new_qty
            inventory_item.cost_price = new_avg_cost
            inventory_item.save()

            InventoryTransaction.objects.create(
                item=inventory_item,
                transaction_type="PURCHASE",
                quantity=qty,
                unit_cost=price,
                reference=invoice.number,
                created_by=request.user
            )

        # 🔹 Journal

        inventory_account = get_object_or_404(Account, code="1800")
        input_vat_account = Account.objects.filter(code="2100").first()
        payable_account = get_object_or_404(Account, code="2010")

        entries = [
            {
                "account": inventory_account.id,
                "debit": float(subtotal),
                "credit": 0
            }
        ]

        if total_vat > 0 and input_vat_account:
            entries.append({
                "account": input_vat_account.id,
                "debit": float(total_vat),
                "credit": 0
            })

        entries.append({
            "account": payable_account.id,
            "debit": 0,
            "credit": float(total)
        })

        journal = ManualJournal.objects.create(
            date=invoice.date,
            currency="AED",
            status="Posted",
            notes=f"Inventory Purchase Invoice - {invoice.number}",
            entries=entries,
            created_by=request.user
        )

        if not journal.is_balanced:
            raise Exception("Journal not balanced")

        invoice.status = "posted"
        invoice.save()

        return Response({
            "success": True,
            "message": "Invoice posted"
        })


class InventoryInvoiceMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        invoice = get_object_or_404(InventoryInvoice, pk=pk)

        if invoice.status != "posted":
            return Response(
                {"error": "Only posted invoices can be marked paid"},
                status=400
            )

        payment_method = request.data.get("payment_method")

        if payment_method not in ["cash", "bank"]:
            return Response(
                {"error": "Invalid payment method"},
                status=400
            )

        total = invoice.total

        if payment_method == "cash":
            payment_account = get_object_or_404(Account, code="1010")
        else:
            payment_account = get_object_or_404(Account, code="1020")

        payable_account = get_object_or_404(Account, code="2010")

        entries = [
            {
                "account": payable_account.id,
                "debit": float(total),
                "credit": 0
            },
            {
                "account": payment_account.id,
                "debit": 0,
                "credit": float(total)
            }
        ]

        journal = ManualJournal.objects.create(
            date=timezone.now().date(),
            currency="AED",
            status="Posted",
            notes=f"Vendor Payment - {invoice.number}",
            entries=entries,
            created_by=request.user
        )

        if not journal.is_balanced:
            raise Exception("Journal not balanced")

        invoice.status = "paid"
        invoice.save()

        return Response({
            "success": True,
            "message": "Invoice marked as paid"
        })




class InventoryInvoicePDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(InventoryInvoice, pk=pk)
        company = CompanyProfile.objects.first()

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename=PurchaseInvoice-{invoice.number}.pdf'
        )

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # ================= HEADER =================

        header_data = []

        if company and company.company_logo:
            logo_data = base64.b64decode(company.company_logo.split(",")[1])
            logo_image = Image(BytesIO(logo_data), width=1.5*inch, height=1.5*inch)
            header_data.append([
                logo_image,
                Paragraph(f"<b>{company.company_name}</b>", styles["Title"])
            ])
        else:
            header_data.append([
                "",
                Paragraph(f"<b>{company.company_name}</b>", styles["Title"])
            ])

        header_table = Table(header_data, colWidths=[2*inch, 4*inch])
        elements.append(header_table)
        elements.append(Spacer(1, 0.3 * inch))

        # ================= COMPANY INFO =================

        company_info = f"""
        {company.company_address}<br/>
        {company.city or ''} {company.state or ''}<br/>
        {company.country} {company.postal_code or ''}<br/>
        Phone: {company.phone_number}<br/>
        Email: {company.email}<br/>
        VAT: {company.vat_number if company.is_vat_registered else "Not Registered"}
        """

        elements.append(Paragraph(company_info, styles["Normal"]))
        elements.append(Spacer(1, 0.5 * inch))

        # ================= PURCHASE INFO =================

        invoice_info = f"""
        <b>Purchase Invoice:</b> {invoice.number}<br/>
        <b>Date:</b> {invoice.date}<br/>
        <b>Due Date:</b> {invoice.due_date or '-'}<br/>
        <b>Status:</b> {invoice.status.upper()}
        """

        elements.append(Paragraph(invoice_info, styles["Normal"]))
        elements.append(Spacer(1, 0.4 * inch))

        # ================= VENDOR =================

        vendor_name = invoice.vendor.company if invoice.vendor else invoice.supplier_name

        elements.append(
            Paragraph(f"<b>Vendor:</b> {vendor_name}", styles["Heading3"])
        )
        elements.append(Spacer(1, 0.3 * inch))

        # ================= ITEMS TABLE =================

        data = [["Item", "Qty", "Unit Cost", "VAT", "Amount"]]

        for item in invoice.items:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            vat_applicable = item.get("vat_applicable", True)

            amount = qty * price

            data.append([
                item.get("item_name") or item.get("description"),
                str(qty),
                f"{price:,.2f}",
                "5%" if vat_applicable else "0%",
                f"{amount:,.2f}",
            ])

        # Totals
        data.append(["", "", "", "Subtotal", f"{invoice.subtotal:,.2f}"])
        data.append(["", "", "", "VAT", f"{invoice.vat:,.2f}"])
        data.append(["", "", "", "Total", f"{invoice.total:,.2f}"])

        table = Table(
            data,
            colWidths=[2*inch, 0.8*inch, 1.2*inch, 0.8*inch, 1.2*inch]
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.8 * inch))

        # ================= SIGNATURE =================

        footer_data = []

        if company.signature_image:
            sig_data = base64.b64decode(company.signature_image.split(",")[1])
            signature = Image(BytesIO(sig_data), width=1.5*inch, height=1*inch)
        else:
            signature = ""

        footer_data.append([
            Paragraph("<b>Authorized Signature</b>", styles["Normal"]),
            ""
        ])
        footer_data.append([signature, ""])

        footer_table = Table(footer_data, colWidths=[3*inch, 3*inch])
        elements.append(footer_table)

        doc.build(elements)

        return response





class InventorySalesInvoiceSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema().get(
            "inventory_sales_invoices", {}
        )

        return Response({
            "success": True,
            "schema": schema
        })



class InventorySalesInvoiceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        try:
            payload = request.data
            items = payload.get("items", [])
            customer_id = payload.get("customer")
            status = payload.get("status", "draft")

            # ==============================
            # VALIDATE STATUS
            # ==============================

            if status not in ["draft", "posted"]:
                return Response(
                    {"error": "Invalid status"},
                    status=400
                )

            # ==============================
            # VALIDATE CUSTOMER
            # ==============================

            if not customer_id:
                return Response(
                    {"error": "Customer is required"},
                    status=400
                )

            customer = get_object_or_404(
                Customer,
                id=customer_id
            )

            if not items:
                return Response(
                    {"error": "At least one item required"},
                    status=400
                )

            # ==============================
            # VALIDATE & CALCULATE TOTALS
            # ==============================

            validated_items = []
            subtotal = Decimal("0.00")
            total_vat = Decimal("0.00")
            total_cogs = Decimal("0.00")

            for item in items:

                inventory_id = item.get("inventory_item")
                if not inventory_id:
                    return Response(
                        {"error": "Inventory item required"},
                        status=400
                    )

                inventory_item = get_object_or_404(
                    InventoryItem,
                    id=inventory_id
                )

                try:
                    qty = Decimal(str(item.get("quantity", 0)))
                    price = Decimal(str(item.get("price", 0)))
                except:
                    return Response(
                        {"error": "Invalid quantity or price"},
                        status=400
                    )

                if qty <= 0:
                    return Response(
                        {"error": "Quantity must be greater than 0"},
                        status=400
                    )

                # Only check stock if posting
                if status == "posted" and inventory_item.current_quantity < qty:
                    return Response(
                        {"error": f"Insufficient stock for {inventory_item.item_name}"},
                        status=400
                    )

                vat_applicable = bool(item.get("vat_applicable", False))

                line_amount = qty * price
                vat_amount = Decimal("0.00")

                if vat_applicable:
                    vat_amount = (
                        line_amount * Decimal("0.05")
                    ).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP
                    )

                subtotal += line_amount
                total_vat += vat_amount

                cost_price = Decimal(str(inventory_item.cost_price))
                total_cogs += cost_price * qty

                validated_items.append({
                    "inventory_item": inventory_id,
                    "quantity": float(qty),
                    "price": float(price),
                    "cost_price": float(cost_price),
                    "vat_applicable": vat_applicable,
                    "line_amount": float(line_amount),
                    "vat_amount": float(vat_amount),
                })

            total = subtotal + total_vat

            # ==============================
            # CREATE INVOICE
            # ==============================

            invoice = InventorySalesInvoice.objects.create(
                customer=customer,
                date=payload.get("date"),
                due_date=payload.get("due_date"),
                status=status,
                items=validated_items,
                subtotal=subtotal,
                vat=total_vat,
                total=total,
                created_by=request.user
            )

            # ====================================================
            # IF POSTED → REDUCE STOCK + CREATE JOURNAL
            # ====================================================

            if status == "posted":

                # 🔹 Reduce stock
                for item in validated_items:

                    inventory_item = InventoryItem.objects.select_for_update().get(
    id=item["inventory_item"]
)

                    qty = Decimal(str(item["quantity"]))
                    inventory_item.current_quantity -= qty
                    inventory_item.save()

                    InventoryTransaction.objects.create(
                        item=inventory_item,
                        transaction_type="SALE",
                        quantity=qty,
                        unit_cost=inventory_item.cost_price,
                        reference=invoice.number,
                        created_by=request.user
                    )

                # 🔹 Journal Entry
                receivable_account = get_object_or_404(Account, code="1100")
                revenue_account = get_object_or_404(Account, code="4000")
                output_vat_account = get_object_or_404(Account, code="2200")
                cogs_account = get_object_or_404(Account, code="5000")
                inventory_account = get_object_or_404(Account, code="1800")

                entries = [

                    # DR Accounts Receivable
                    {
                        "account": receivable_account.id,
                        "debit": float(total),
                        "credit": 0
                    },

                    # CR Revenue
                    {
                        "account": revenue_account.id,
                        "debit": 0,
                        "credit": float(subtotal)
                    }
                ]

                if total_vat > 0:
                    entries.append({
                        "account": output_vat_account.id,
                        "debit": 0,
                        "credit": float(total_vat)
                    })

                # DR COGS
                entries.append({
                    "account": cogs_account.id,
                    "debit": float(total_cogs),
                    "credit": 0
                })

                # CR Inventory
                entries.append({
                    "account": inventory_account.id,
                    "debit": 0,
                    "credit": float(total_cogs)
                })

                journal = ManualJournal.objects.create(
                    date=invoice.date,
                    currency="AED",
                    status="Posted",
                    notes=f"Inventory Sales Invoice - {invoice.number}",
                    entries=entries,
                    created_by=request.user
                )

                if not journal.is_balanced:
                    raise Exception("Journal not balanced")

            return Response({
                "success": True,
                "invoice_id": invoice.id,
                "number": invoice.number
            }, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=400)



class InventorySalesInvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema().get(
            "inventory_sales_invoices", {}
        )
        columns = schema.get("table_columns", [])

        invoices = InventorySalesInvoice.objects.select_related(
            "customer"
        ).all()

        data = []

        for invoice in invoices:
            row = {"id": invoice.id}

            for col in columns:

                if col == "customer":
                    row[col] = (
                        invoice.customer.company
                        if invoice.customer else None
                    )

                elif hasattr(invoice, col):
                    value = getattr(invoice, col)
                    row[col] = (
                        str(value)
                        if isinstance(value, Decimal)
                        else value
                    )

                else:
                    row[col] = None

            data.append(row)

        return Response({
            "success": True,
            "columns": columns,
            "rows": data
        })



class InventorySalesInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        invoice = get_object_or_404(
            InventorySalesInvoice,
            pk=pk
        )

        item_data = []

        for item in invoice.items:

            inventory_id = item.get("inventory_item")
            inventory_name = None
            item_code = None

            if inventory_id:
                try:
                    inventory = InventoryItem.objects.get(id=inventory_id)
                    inventory_name = inventory.item_name
                    item_code = inventory.item_code
                except InventoryItem.DoesNotExist:
                    pass

            item_data.append({
                "inventory_item": inventory_id,
                "item_code": item_code,
                "item_name": inventory_name,
                "quantity": item.get("quantity"),
                "price": item.get("price"),
                "vat_applicable": item.get("vat_applicable"),
                "line_amount": item.get("line_amount"),
                "vat_amount": item.get("vat_amount"),
            })

        data = {
            "id": invoice.id,
            "number": invoice.number,
            "customer": {
                "id": invoice.customer.id if invoice.customer else None,
                "name": invoice.customer.company if invoice.customer else None,
            },
            "date": invoice.date,
            "due_date": invoice.due_date,
            "status": invoice.status,

            "subtotal": str(invoice.subtotal),
            "vat": str(invoice.vat),
            "total": str(invoice.total),

            "items": item_data,

            "created_at": invoice.created_at,
        }

        return Response({
            "success": True,
            "inventory_sales_invoice": data
        })



class InventorySalesInvoicePostView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        invoice = get_object_or_404(
            InventorySalesInvoice,
            pk=pk
        )

        if invoice.status != "draft":
            return Response(
                {"error": "Only draft invoices can be posted"},
                status=400
            )

        subtotal = Decimal(str(invoice.subtotal))
        total_vat = Decimal(str(invoice.vat))
        total = Decimal(str(invoice.total))
        total_cogs = Decimal("0.00")

        # ====================================
        # 🔹 Reduce Stock
        # ====================================

        for item in invoice.items:

            inventory_item = InventoryItem.objects.select_for_update().get(
                id=item["inventory_item"]
            )

            qty = Decimal(str(item["quantity"]))

            if inventory_item.current_quantity < qty:
                return Response(
                    {"error": f"Insufficient stock for {inventory_item.item_name}"},
                    status=400
                )

            cost_price = Decimal(str(inventory_item.cost_price))
            total_cogs += cost_price * qty

            inventory_item.current_quantity -= qty
            inventory_item.save()

            InventoryTransaction.objects.create(
                item=inventory_item,
                transaction_type="SALE",
                quantity=qty,
                unit_cost=cost_price,
                reference=invoice.number,
                created_by=request.user
            )

        # ====================================
        # 🔹 Journal Entry
        # ====================================

        receivable_account = get_object_or_404(Account, code="1100")
        revenue_account = get_object_or_404(Account, code="4000")
        output_vat_account = get_object_or_404(Account, code="2200")
        cogs_account = get_object_or_404(Account, code="5000")
        inventory_account = get_object_or_404(Account, code="1800")

        entries = [

            {
                "account": receivable_account.id,
                "debit": float(total),
                "credit": 0
            },

            {
                "account": revenue_account.id,
                "debit": 0,
                "credit": float(subtotal)
            }
        ]

        if total_vat > 0:
            entries.append({
                "account": output_vat_account.id,
                "debit": 0,
                "credit": float(total_vat)
            })

        entries.append({
            "account": cogs_account.id,
            "debit": float(total_cogs),
            "credit": 0
        })

        entries.append({
            "account": inventory_account.id,
            "debit": 0,
            "credit": float(total_cogs)
        })

        journal = ManualJournal.objects.create(
            date=invoice.date,
            currency="AED",
            status="Posted",
            notes=f"Inventory Sales Invoice - {invoice.number}",
            entries=entries,
            created_by=request.user
        )

        if not journal.is_balanced:
            raise Exception("Journal not balanced")

        invoice.status = "posted"
        invoice.save()

        return Response({
            "success": True,
            "message": "Invoice posted successfully"
        })




class InventorySalesInvoiceMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):

        invoice = get_object_or_404(
            InventorySalesInvoice,
            pk=pk
        )

        if invoice.status != "posted":
            return Response(
                {"error": "Only posted invoices can be marked paid"},
                status=400
            )

        payment_method = request.data.get("payment_method")

        if payment_method not in ["cash", "bank"]:
            return Response(
                {"error": "Payment method must be cash or bank"},
                status=400
            )

        total = Decimal(str(invoice.total))

        # 🔹 Choose correct account
        if payment_method == "cash":
            payment_account = get_object_or_404(Account, code="1010")  # Cash
        else:
            payment_account = get_object_or_404(Account, code="1020")  # Bank

        receivable_account = get_object_or_404(Account, code="1100")

        entries = [
            {
                "account": payment_account.id,
                "debit": float(total),
                "credit": 0
            },
            {
                "account": receivable_account.id,
                "debit": 0,
                "credit": float(total)
            }
        ]

        journal = ManualJournal.objects.create(
            date=timezone.now().date(),
            currency="AED",
            status="Posted",
            notes=f"Payment Received ({payment_method.upper()}) - {invoice.number}",
            entries=entries,
            created_by=request.user
        )

        if not journal.is_balanced:
            raise Exception("Journal not balanced")

        invoice.status = "paid"
        invoice.save()

        return Response({
            "success": True,
            "message": "Invoice marked as paid"
        })



from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, Image
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from io import BytesIO
import base64


class InventorySalesInvoicePDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        invoice = get_object_or_404(
            InventorySalesInvoice,
            pk=pk
        )

        company = CompanyProfile.objects.first()

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename=SalesInvoice-{invoice.number}.pdf'
        )

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # ================= HEADER =================

        header_data = []

        if company and company.company_logo:
            logo_data = base64.b64decode(
                company.company_logo.split(",")[1]
            )
            logo_image = Image(
                BytesIO(logo_data),
                width=1.5 * inch,
                height=1.5 * inch
            )

            header_data.append([
                logo_image,
                Paragraph(
                    f"<b>{company.company_name}</b>",
                    styles["Title"]
                )
            ])
        else:
            header_data.append([
                "",
                Paragraph(
                    f"<b>{company.company_name}</b>",
                    styles["Title"]
                )
            ])

        header_table = Table(
            header_data,
            colWidths=[2 * inch, 4 * inch]
        )

        elements.append(header_table)
        elements.append(Spacer(1, 0.3 * inch))

        # ================= COMPANY INFO =================

        company_info = f"""
        {company.company_address}<br/>
        {company.city or ''} {company.state or ''}<br/>
        {company.country} {company.postal_code or ''}<br/>
        Phone: {company.phone_number}<br/>
        Email: {company.email}<br/>
        VAT: {company.vat_number if company.is_vat_registered else "Not Registered"}
        """

        elements.append(
            Paragraph(company_info, styles["Normal"])
        )
        elements.append(Spacer(1, 0.5 * inch))

        # ================= SALES INFO =================

        invoice_info = f"""
        <b>Sales Invoice:</b> {invoice.number}<br/>
        <b>Date:</b> {invoice.date}<br/>
        <b>Due Date:</b> {invoice.due_date or '-'}<br/>
        <b>Status:</b> {invoice.status.upper()}
        """

        elements.append(
            Paragraph(invoice_info, styles["Normal"])
        )
        elements.append(Spacer(1, 0.4 * inch))

        # ================= CUSTOMER =================

        customer_name = (
            invoice.customer.company
            if invoice.customer else "Walk-in Customer"
        )

        elements.append(
            Paragraph(
                f"<b>Customer:</b> {customer_name}",
                styles["Heading3"]
            )
        )
        elements.append(Spacer(1, 0.3 * inch))

        # ================= ITEMS TABLE =================

        data = [["Item", "Qty", "Unit Price", "VAT", "Amount"]]

        for item in invoice.items:

            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            vat_amount = Decimal(str(item.get("vat_amount", 0)))
            line_amount = Decimal(str(item.get("line_amount", 0)))

            total_line = line_amount + vat_amount

            data.append([
                item.get("item_name"),
                str(qty),
                f"{price:,.2f}",
                f"{vat_amount:,.2f}",
                f"{total_line:,.2f}",
            ])

        # ================= TOTALS =================

        data.append(["", "", "", "Subtotal", f"{invoice.subtotal:,.2f}"])
        data.append(["", "", "", "VAT", f"{invoice.vat:,.2f}"])
        data.append(["", "", "", "Total", f"{invoice.total:,.2f}"])

        table = Table(
            data,
            colWidths=[2 * inch, 0.8 * inch, 1.2 * inch, 1 * inch, 1.2 * inch]
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.8 * inch))

        # ================= SIGNATURE =================

        footer_data = []

        if company.signature_image:
            sig_data = base64.b64decode(
                company.signature_image.split(",")[1]
            )
            signature = Image(
                BytesIO(sig_data),
                width=1.5 * inch,
                height=1 * inch
            )
        else:
            signature = ""

        footer_data.append([
            Paragraph(
                "<b>Authorized Signature</b>",
                styles["Normal"]
            ),
            ""
        ])

        footer_data.append([signature, ""])

        footer_table = Table(
            footer_data,
            colWidths=[3 * inch, 3 * inch]
        )

        elements.append(footer_table)

        doc.build(elements)

        return response
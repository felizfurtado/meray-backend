from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import *
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum , Q
from django.utils.timezone import now
from django.db.models import Sum, Count
from decimal import Decimal

import uuid

import csv
import io

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.db import connection

User = get_user_model()


def debug_schema(request):
    return HttpResponse(f"Schema: {connection.schema_name}")

class UserListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        users = User.objects.all()

        data = []

        for user in users:

            data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "date_joined": user.date_joined
            })

        return Response({
            "success": True,
            "users": data
        })

        

class NavigationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        schema = request.tenant.get_schema()

        navigation = schema.get("navigation", {})

        operations = navigation.get("operations", {})
        sales = navigation.get("sales", {})
        bank = navigation.get("bank", {})
        wps = navigation.get("wps", {})

        return Response({
            "success": True,
            "operations": operations,
            "sales": sales,
            "bank": bank,
            "wps": wps
        })






class SchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "tenant": request.tenant.name,
            "schema": request.tenant.get_leads_schema()
        })




from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import TruncMonth

# class DashboardView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):

#         total_leads = Lead.objects.count()
#         total_customers = Customer.objects.count()
#         total_invoices = Invoice.objects.count()
#         total_inventory = InventoryItem.objects.count()


#         invoice_revenue = Invoice.objects.filter(
#             status__iexact="paid"
#         ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

#         inventory_revenue = InventorySalesInvoice.objects.filter(
#             status__iexact="paid"
#         ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

#         total_revenue = invoice_revenue + inventory_revenue


#         outstanding = Invoice.objects.filter(
#             status__in=["sent", "overdue"]
#         ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")


#         cogs = Decimal("0.00")

#         inventory_sales = InventorySalesInvoice.objects.filter(
#             status__iexact="paid"
#         )

#         for sale in inventory_sales:
#             for item in sale.items:

#                 qty = Decimal(str(item.get("quantity", 0)))
#                 cost = Decimal(str(item.get("cost_price", 0)))

#                 cogs += qty * cost


#         gross_profit = total_revenue - cogs


#         total_expenses = Expense.objects.filter(
#             status="POSTED"
#         ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")


#         net_profit = gross_profit - total_expenses

#         recent_invoices = Invoice.objects.order_by("-created_at")[:5]
#         recent_leads = Lead.objects.order_by("-created_at")[:5]

#         return Response({
#             "summary": {
#                 "total_leads": total_leads,
#                 "total_customers": total_customers,
#                 "total_invoices": total_invoices,
#                 "total_inventory": total_inventory,

#                 "total_revenue": float(total_revenue),
#                 "outstanding": float(outstanding),

#                 "gross_profit": float(gross_profit),
#                 "net_profit": float(net_profit),
#                 "total_expenses": float(total_expenses),
#             },

#             "recent_invoices": [
#                 {
#                     "id": i.id,
#                     "number": i.number,
#                     "customer": i.customer.company if i.customer else "Custom",
#                     "total": float(i.total),
#                     "status": i.status
#                 }
#                 for i in recent_invoices
#             ],

#             "recent_leads": [
#                 {
#                     "id": l.id,
#                     "name": l.name,
#                     "company": l.company
#                 }
#                 for l in recent_leads
#             ]
#         })




class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        today = timezone.now().date()

        # ===============================
        # BASIC COUNTS
        # ===============================

        total_leads = Lead.objects.count()
        total_customers = Customer.objects.count()
        total_invoices = Invoice.objects.count() + InventorySalesInvoice.objects.count()
        total_inventory = InventoryItem.objects.count()

        # ===============================
        # REVENUE
        # ===============================

        invoice_revenue = Invoice.objects.filter(
            status__iexact="paid"
        ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        inventory_revenue = InventorySalesInvoice.objects.filter(
            status__iexact="paid"
        ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        total_revenue = invoice_revenue + inventory_revenue

        # ===============================
        # OUTSTANDING
        # ===============================

        outstanding_invoice = Invoice.objects.filter(
            status__in=["sent", "posted"]
        ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        outstanding_inventory = InventorySalesInvoice.objects.filter(
            status__in=["sent", "posted"]
        ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        outstanding = outstanding_invoice + outstanding_inventory

        # ===============================
        # COGS (INVENTORY SALES ONLY)
        # ===============================

        cogs = Decimal("0.00")

        inventory_sales = InventorySalesInvoice.objects.filter(
            status__iexact="paid"
        )

        for sale in inventory_sales:
            for item in sale.items:

                qty = Decimal(str(item.get("quantity", 0)))
                cost = Decimal(str(item.get("cost_price", 0)))

                cogs += qty * cost

        # ===============================
        # GROSS PROFIT
        # ===============================

        gross_profit = total_revenue - cogs

        # ===============================
        # EXPENSES
        # ===============================

        total_expenses = Expense.objects.filter(
            status="POSTED"
        ).aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        # ===============================
        # NET PROFIT
        # ===============================

        net_profit = gross_profit - total_expenses

        # ===============================
        # RECEIVABLES
        # ===============================

        # ---------- DRAFT ----------

        draft_invoices = Invoice.objects.filter(status="draft")
        draft_inventory = InventorySalesInvoice.objects.filter(status="draft")

        draft_count = draft_invoices.count() + draft_inventory.count()

        draft_total = (
            (draft_invoices.aggregate(total=Sum("total"))["total"] or Decimal("0.00"))
            +
            (draft_inventory.aggregate(total=Sum("total"))["total"] or Decimal("0.00"))
        )

        # ---------- AWAITING ----------

        awaiting_invoices = Invoice.objects.filter(
            status__in=["sent", "posted"]
        ).filter(
            Q(due_date__gte=today) | Q(due_date__isnull=True)
        )

        awaiting_inventory = InventorySalesInvoice.objects.filter(
            status__in=["sent", "posted"]
        ).filter(
            Q(due_date__gte=today) | Q(due_date__isnull=True)
        )

        awaiting_count = awaiting_invoices.count() + awaiting_inventory.count()

        awaiting_total = (
            (awaiting_invoices.aggregate(total=Sum("total"))["total"] or Decimal("0.00"))
            +
            (awaiting_inventory.aggregate(total=Sum("total"))["total"] or Decimal("0.00"))
        )

        # ---------- OVERDUE ----------

        overdue_invoices = Invoice.objects.filter(
            status__in=["sent", "posted"],
            due_date__lt=today
        )

        overdue_inventory = InventorySalesInvoice.objects.filter(
            status__in=["sent", "posted"],
            due_date__lt=today
        )

        overdue_count = overdue_invoices.count() + overdue_inventory.count()

        overdue_total = (
            (overdue_invoices.aggregate(total=Sum("total"))["total"] or Decimal("0.00"))
            +
            (overdue_inventory.aggregate(total=Sum("total"))["total"] or Decimal("0.00"))
        )

        # ===============================
        # MONTHLY CHART
        # ===============================

        monthly_invoices = (
            Invoice.objects
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Sum("total"))
            .order_by("month")
        )

        invoice_chart = [
            {
                "month": m["month"].strftime("%b"),
                "total": float(m["total"] or 0)
            }
            for m in monthly_invoices
        ]

        # ===============================
        # RECENT DATA
        # ===============================

        recent_invoices = Invoice.objects.order_by("-created_at")[:5]
        recent_leads = Lead.objects.order_by("-created_at")[:5]

        # ===============================
        # RESPONSE
        # ===============================

        return Response({

            "summary": {
                "total_leads": total_leads,
                "total_customers": total_customers,
                "total_invoices": total_invoices,
                "total_inventory": total_inventory,

                "total_revenue": float(total_revenue),
                "outstanding": float(outstanding),

                "gross_profit": float(gross_profit),
                "net_profit": float(net_profit),
                "total_expenses": float(total_expenses),
            },

            "receivables": {
                "drafts": {
                    "count": draft_count,
                    "total": float(draft_total)
                },
                "awaiting": {
                    "count": awaiting_count,
                    "total": float(awaiting_total)
                },
                "overdue": {
                    "count": overdue_count,
                    "total": float(overdue_total)
                },
                "chart": invoice_chart
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



            
            import os

            upload_dir = os.path.join(os.getcwd(), "attachments")
            
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            
            files = request.FILES.getlist("attachments")
            
            for file in files:
                file_path = os.path.join(upload_dir, file.name)
            
                with open(file_path, "wb+") as f:
                    for chunk in file.chunks():
                        f.write(chunk)
            
                ExpenseAttachment.objects.create(
                    expense=expense,
                    file=file_path,
                    file_name=file.name
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


# class ExpenseDetailView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, pk):
#         expense = get_object_or_404(
#             Expense.objects.select_related(
#                 "vendor",
#                 "account",
#                 "payment_account"
#             ),
#             pk=pk
#         )

#         return Response({
#             "success": True,
#             "expense": {
#                 "id": expense.id,
#                 "expense_number": expense.expense_number,
#                 "date": expense.date,

#                 # Vendor
#                 "vendor": expense.vendor.id if expense.vendor else None,
#                 "vendor_name": (
#                     expense.vendor.company
#                     if expense.vendor else None
#                 ),

#                 "currency": expense.currency,
#                 "amount": float(expense.amount),
#                 "vat_applicable": expense.vat_applicable,
#                 "vat_amount": float(expense.vat_amount),
#                 "total": float(expense.total),

#                 # Expense Account
#                 "account": expense.account.id if expense.account else None,
#                 "account_name": (
#                     f"{expense.account.code} - {expense.account.name}"
#                     if expense.account else None
#                 ),

#                 # 🔥 Payment Account (THIS replaces payment_method)
#                 "payment_account": expense.payment_account.id if expense.payment_account else None,
#                 "payment_account_name": (
#                     f"{expense.payment_account.code} - {expense.payment_account.name}"
#                     if expense.payment_account else None
#                 ),

#                 "status": expense.status,
#                 "notes": expense.notes,
#                 "extra_data": expense.extra_data,
#                 "created_by": expense.created_by.username if expense.created_by else None,
#                 "created_at": expense.created_at,
#                 "updated_at": expense.updated_at,
#             }
#         })

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

        # 🔥 GET ATTACHMENTS
        attachments = [
            {
                "id": att.id,
                "file": f"/attachments/{att.id}/",   # if using FileField
                "name": att.file_name,
                "download_url": f"/attachments/{att.id}/"
            }
            for att in expense.attachments.all()
        ]

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

                # Payment Account
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

                # 🔥 ATTACHMENTS ADDED HERE
                "attachments": attachments
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

        # ================= CUSTOMER =================

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

        # ================= ITEMS =================

        prepared_items = []

        for item in invoice.items:

            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            amount = Decimal(str(item.get("amount", 0)))

            prepared_items.append({
                "description": item.get("description", ""),
                "quantity": qty,
                "price": f"{price:,.2f}",
                "amount": f"{amount:,.2f}"
            })

        # ================= TITLE =================

        invoice_title = "Tax Invoice" if invoice.vat and invoice.vat > 0 else "Invoice"

        # ================= CONTEXT =================

        context = {

            "company": company,

            "invoice": {
                "number": invoice.number,
                "date": invoice.date.strftime("%d %b %Y"),
                "due_date": invoice.due_date.strftime("%d %b %Y") if invoice.due_date else "N/A",
                "status": invoice.status,
            },

            "invoice_title": invoice_title,

            "customer": customer,

            "items": prepared_items,

            "subtotal": f"{invoice.subtotal:,.2f}",
            "vat": f"{invoice.vat:,.2f}",
            "total": f"{invoice.total:,.2f}",

            "generation_date": timezone.now().strftime("%d %b %Y, %I:%M %p"),
        }

        # ================= TEMPLATE =================

        template = get_template("pdf/invoice.html")
        html = template.render(context)

        # ================= PDF =================

        result = BytesIO()

        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")),
            result
        )

        if not pdf.err:

            response = HttpResponse(
                result.getvalue(),
                content_type="application/pdf"
            )

            response["Content-Disposition"] = f'attachment; filename=Invoice-{invoice.number}.pdf'

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

# class InvoiceAdjustmentPDFView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, pk):

#         adjustment = get_object_or_404(
#             Invoice,
#             pk=pk,
#             document_type__in=["CREDIT_NOTE", "DEBIT_NOTE"]
#         )

#         company = CompanyProfile.objects.first()
#         original_invoice = adjustment.related_invoice

#         response = HttpResponse(content_type="application/pdf")
#         response["Content-Disposition"] = (
#             f'attachment; filename={adjustment.document_type}-{adjustment.number}.pdf'
#         )

#         doc = SimpleDocTemplate(response, pagesize=A4)
#         elements = []
#         styles = getSampleStyleSheet()


#         title_text = "CREDIT NOTE" if adjustment.document_type == "CREDIT_NOTE" else "DEBIT NOTE"

#         elements.append(Paragraph(f"<b>{title_text}</b>", styles["Title"]))
#         elements.append(Spacer(1, 0.3 * inch))


#         if company:
#             company_info = f"""
#             <b>{company.company_name}</b><br/>
#             {company.company_address}<br/>
#             {company.city or ''} {company.state or ''}<br/>
#             {company.country}<br/>
#             VAT: {company.vat_number if company.is_vat_registered else "Not Registered"}
#             """

#             elements.append(Paragraph(company_info, styles["Normal"]))
#             elements.append(Spacer(1, 0.4 * inch))


#         info_text = f"""
#         <b>Number:</b> {adjustment.number}<br/>
#         <b>Date:</b> {adjustment.date}<br/>
#         <b>Status:</b> {adjustment.status.upper()}
#         """

#         if original_invoice:
#             info_text += f"<br/><b>Related Invoice:</b> {original_invoice.number}"

#         elements.append(Paragraph(info_text, styles["Normal"]))
#         elements.append(Spacer(1, 0.4 * inch))


#         customer_name = adjustment.customer.company if adjustment.customer else ""
#         elements.append(Paragraph(f"<b>Customer:</b> {customer_name}", styles["Heading3"]))
#         elements.append(Spacer(1, 0.3 * inch))


#         data = [["Description", "Qty", "Price", "Amount"]]

#         subtotal = Decimal("0.00")

#         for item in adjustment.items:
#             qty = Decimal(str(item.get("quantity", 0)))
#             price = Decimal(str(item.get("price", 0)))
#             amount = qty * price
#             subtotal += amount

#             data.append([
#                 item.get("description"),
#                 str(qty),
#                 f"{price:,.2f}",
#                 f"{amount:,.2f}",
#             ])

#         vat = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
#         total = subtotal + vat

#         data.append(["", "", "Subtotal", f"{subtotal:,.2f}"])
#         data.append(["", "", "VAT (5%)", f"{vat:,.2f}"])
#         data.append(["", "", "Total", f"{total:,.2f}"])

#         table = Table(data, colWidths=[2.5*inch, 0.8*inch, 1.2*inch, 1.2*inch])

#         table.setStyle(TableStyle([
#             ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
#             ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
#             ("ALIGN", (1,1), (-1,-1), "RIGHT"),
#         ]))

#         elements.append(table)
#         elements.append(Spacer(1, 0.5 * inch))


#         if adjustment.document_type == "CREDIT_NOTE" and original_invoice:

#             previous_credits = Invoice.objects.filter(
#                 related_invoice=original_invoice,
#                 document_type="CREDIT_NOTE"
#             ).exclude(id=adjustment.id).aggregate(
#                 total_sum=Sum("total")
#             )["total_sum"] or Decimal("0.00")

#             remaining_balance = (
#                 original_invoice.total - previous_credits - total
#             )

#             elements.append(
#                 Paragraph(
#                     f"<b>Remaining Invoice Balance:</b> {remaining_balance:,.2f}",
#                     styles["Normal"]
#                 )
#             )

#         doc.build(elements)

#         return response
    

    

from django.template.loader import get_template
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from io import BytesIO
from xhtml2pdf import pisa
from django.db.models import Sum


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

        title = "Credit Note" if adjustment.document_type == "CREDIT_NOTE" else "Debit Note"

        # ================= CUSTOMER =================

        customer_name = adjustment.customer.company if adjustment.customer else ""

        # ================= ITEMS =================

        prepared_items = []
        subtotal = Decimal("0.00")

        for item in adjustment.items:

            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            amount = qty * price

            subtotal += amount

            prepared_items.append({
                "description": item.get("description", ""),
                "quantity": qty,
                "price": f"{price:,.2f}",
                "amount": f"{amount:,.2f}",
            })

        vat = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        total = subtotal + vat

        # ================= REMAINING BALANCE =================

        remaining_balance = None

        if adjustment.document_type == "CREDIT_NOTE" and original_invoice:

            previous_credits = Invoice.objects.filter(
                related_invoice=original_invoice,
                document_type="CREDIT_NOTE"
            ).exclude(id=adjustment.id).aggregate(
                total_sum=Sum("total")
            )["total_sum"] or Decimal("0.00")

            remaining_balance = original_invoice.total - previous_credits - total

        # ================= CONTEXT =================

        context = {
            "company": company,
            "adjustment": adjustment,
            "title": title,
            "customer_name": customer_name,
            "items": prepared_items,
            "subtotal": f"{subtotal:,.2f}",
            "vat": f"{vat:,.2f}",
            "total": f"{total:,.2f}",
            "remaining_balance": remaining_balance,
            "original_invoice": original_invoice
        }

        template = get_template("pdf/adjustment_note.html")
        html = template.render(context)

        result = BytesIO()

        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")),
            result
        )

        if not pdf.err:

            response = HttpResponse(
                result.getvalue(),
                content_type="application/pdf"
            )

            response["Content-Disposition"] = f'attachment; filename={adjustment.document_type}-{adjustment.number}.pdf'

            return response

        return HttpResponse("Error generating PDF", status=500)



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

            accounts_payable = get_object_or_404(Account, code="2010")  # fixed AP

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

            # Validate invoice
            if invoice.status == "Paid":
                return Response({"error": "Invoice already paid"}, status=400)

            if invoice.status != "Posted":
                return Response({"error": "Only posted invoices can be paid"}, status=400)

            bank_account_code = request.data.get("bank_account")

            if not bank_account_code:
                return Response({"error": "Bank or Cash account required"}, status=400)

            # SIMPLIFIED: Just get the account directly from the code
            try:
                bank_account = Account.objects.get(code=bank_account_code)
            except Account.DoesNotExist:
                return Response({
                    "error": f"Account with code '{bank_account_code}' not found",
                    "available_codes": list(Account.objects.filter(
                        code__in=["1010", "1020"]
                    ).values_list('code', flat=True))
                }, status=400)

            # Accounts Payable
            try:
                accounts_payable = Account.objects.get(code="2010")
            except Account.DoesNotExist:
                return Response({"error": "Accounts Payable account (2010) not found"}, status=400)

            # Journal entries
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

            # Update invoice
            invoice.status = "Paid"
            invoice.save()

            return Response({
                "success": True,
                "journal_id": journal.id
            })

        except Exception as e:
            return Response({"error": str(e)}, status=400)



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


# class InventorySalesInvoicePDFView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, pk):

#         invoice = get_object_or_404(
#             InventorySalesInvoice,
#             pk=pk
#         )

#         company = CompanyProfile.objects.first()

#         response = HttpResponse(content_type="application/pdf")
#         response["Content-Disposition"] = (
#             f'attachment; filename=SalesInvoice-{invoice.number}.pdf'
#         )

#         doc = SimpleDocTemplate(response, pagesize=A4)
#         elements = []
#         styles = getSampleStyleSheet()


#         header_data = []

#         if company and company.company_logo:
#             logo_data = base64.b64decode(
#                 company.company_logo.split(",")[1]
#             )
#             logo_image = Image(
#                 BytesIO(logo_data),
#                 width=1.5 * inch,
#                 height=1.5 * inch
#             )

#             header_data.append([
#                 logo_image,
#                 Paragraph(
#                     f"<b>{company.company_name}</b>",
#                     styles["Title"]
#                 )
#             ])
#         else:
#             header_data.append([
#                 "",
#                 Paragraph(
#                     f"<b>{company.company_name}</b>",
#                     styles["Title"]
#                 )
#             ])

#         header_table = Table(
#             header_data,
#             colWidths=[2 * inch, 4 * inch]
#         )

#         elements.append(header_table)
#         elements.append(Spacer(1, 0.3 * inch))


#         company_info = f"""
#         {company.company_address}<br/>
#         {company.city or ''} {company.state or ''}<br/>
#         {company.country} {company.postal_code or ''}<br/>
#         Phone: {company.phone_number}<br/>
#         Email: {company.email}<br/>
#         VAT: {company.vat_number if company.is_vat_registered else "Not Registered"}
#         """

#         elements.append(
#             Paragraph(company_info, styles["Normal"])
#         )
#         elements.append(Spacer(1, 0.5 * inch))


#         invoice_info = f"""
#         <b>Sales Invoice:</b> {invoice.number}<br/>
#         <b>Date:</b> {invoice.date}<br/>
#         <b>Due Date:</b> {invoice.due_date or '-'}<br/>
#         <b>Status:</b> {invoice.status.upper()}
#         """

#         elements.append(
#             Paragraph(invoice_info, styles["Normal"])
#         )
#         elements.append(Spacer(1, 0.4 * inch))

#         customer_name = (
#             invoice.customer.company
#             if invoice.customer else "Walk-in Customer"
#         )

#         elements.append(
#             Paragraph(
#                 f"<b>Customer:</b> {customer_name}",
#                 styles["Heading3"]
#             )
#         )
#         elements.append(Spacer(1, 0.3 * inch))


#         data = [["Item", "Qty", "Unit Price", "VAT", "Amount"]]

#         for item in invoice.items:

#             qty = Decimal(str(item.get("quantity", 0)))
#             price = Decimal(str(item.get("price", 0)))
#             vat_amount = Decimal(str(item.get("vat_amount", 0)))
#             line_amount = Decimal(str(item.get("line_amount", 0)))

#             total_line = line_amount + vat_amount

#             data.append([
#                 item.get("item_name"),
#                 str(qty),
#                 f"{price:,.2f}",
#                 f"{vat_amount:,.2f}",
#                 f"{total_line:,.2f}",
#             ])

#         # ================= TOTALS =================

#         data.append(["", "", "", "Subtotal", f"{invoice.subtotal:,.2f}"])
#         data.append(["", "", "", "VAT", f"{invoice.vat:,.2f}"])
#         data.append(["", "", "", "Total", f"{invoice.total:,.2f}"])

#         table = Table(
#             data,
#             colWidths=[2 * inch, 0.8 * inch, 1.2 * inch, 1 * inch, 1.2 * inch]
#         )

#         table.setStyle(TableStyle([
#             ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
#             ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
#             ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
#             ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
#         ]))

#         elements.append(table)
#         elements.append(Spacer(1, 0.8 * inch))

#         # ================= SIGNATURE =================

#         footer_data = []

#         if company.signature_image:
#             sig_data = base64.b64decode(
#                 company.signature_image.split(",")[1]
#             )
#             signature = Image(
#                 BytesIO(sig_data),
#                 width=1.5 * inch,
#                 height=1 * inch
#             )
#         else:
#             signature = ""

#         footer_data.append([
#             Paragraph(
#                 "<b>Authorized Signature</b>",
#                 styles["Normal"]
#             ),
#             ""
#         ])

#         footer_data.append([signature, ""])

#         footer_table = Table(
#             footer_data,
#             colWidths=[3 * inch, 3 * inch]
#         )

#         elements.append(footer_table)

#         doc.build(elements)

#         return response






class InventorySalesInvoicePDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        invoice = get_object_or_404(InventorySalesInvoice, pk=pk)
        company = CompanyProfile.objects.first()

        prepared_items = []

        for item in invoice.items:

            item_id = item.get("inventory_item")

            try:
                inventory = InventoryItem.objects.get(id=item_id)
                item_name = inventory.item_name
            except InventoryItem.DoesNotExist:
                item_name = "Unknown Item"

            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            vat_amount = Decimal(str(item.get("vat_amount", 0)))
            line_amount = Decimal(str(item.get("line_amount", 0)))

            total_line = line_amount + vat_amount

            prepared_items.append({
                "item_name": item_name,
                "quantity": qty,
                "price": price,
                "vat_amount": vat_amount,
                "total": total_line
            })

        template = get_template("pdf/inventorysalesinvoice.html")
        invoice_title = "Tax Invoice" if invoice.vat and invoice.vat > 0 else "Invoice"
        context = {
            "invoice": invoice,
            "company": company,
            "items": prepared_items,
            "invoice_title": invoice_title
        }

        html = template.render(context)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename=SalesInvoice-{invoice.number}.pdf'

        pisa_status = pisa.CreatePDF(
            html,
            dest=response
        )

        if pisa_status.err:
            return HttpResponse("PDF generation error")

        return response


class ProfitLossReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not start_date or not end_date:
            return Response({
                "success": False,
                "error": "start_date and end_date required"
            }, status=400)

        journals = ManualJournal.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            status="Posted"
        )

        revenue_accounts = {}
        cogs_total = Decimal("0.00")
        expense_accounts = {}

        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")

        for journal in journals:

            for entry in journal.entries:

                account_id = entry.get("account")
                debit = Decimal(str(entry.get("debit", 0)))
                credit = Decimal(str(entry.get("credit", 0)))

                try:
                    account = Account.objects.get(id=account_id)
                except Account.DoesNotExist:
                    continue

                # =========================
                # REVENUE
                # =========================

                if account.type == "Revenue":

                    revenue_accounts.setdefault(account.id, {
                        "name": account.name,
                        "code": account.code,
                        "total": Decimal("0.00")
                    })

                    revenue_accounts[account.id]["total"] += credit
                    total_revenue += credit

                # =========================
                # COGS (5000)
                # =========================

                elif account.code == "5000":

                    cogs_total += debit

                # =========================
                # OTHER EXPENSES
                # =========================

                elif account.type == "Expense":

                    expense_accounts.setdefault(account.id, {
                        "name": account.name,
                        "code": account.code,
                        "total": Decimal("0.00")
                    })

                    expense_accounts[account.id]["total"] += debit
                    total_expenses += debit


        gross_profit = total_revenue - cogs_total
        net_profit = gross_profit - total_expenses


        return Response({

            "operating_income": [
                {
                    "account": v["name"],
                    "code": v["code"],
                    "total": float(v["total"])
                }
                for v in revenue_accounts.values()
            ],

            "total_operating_income": float(total_revenue),

            "cogs": float(cogs_total),

            "gross_profit": float(gross_profit),

            "operating_expenses": [
                {
                    "account": v["name"],
                    "code": v["code"],
                    "total": float(v["total"])
                }
                for v in expense_accounts.values()
            ],

            "total_operating_expenses": float(total_expenses),

            "net_profit": float(net_profit)

        })




# class BalanceSheetView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):

#         report_date = request.query_params.get("date")

#         if not report_date:
#             return Response({"error": "date is required"}, status=400)

#         journals = ManualJournal.objects.filter(
#             date__lte=report_date,
#             status="Posted"
#         )

#         assets = {}
#         liabilities = {}
#         equity = {}

#         total_assets = Decimal("0")
#         total_liabilities = Decimal("0")
#         total_equity = Decimal("0")


#         accounts = {a.id: a for a in Account.objects.all()}

#         for journal in journals:

#             for entry in journal.entries:

#                 account = accounts.get(entry["account"])

#                 if not account:
#                     continue

#                 debit = Decimal(str(entry.get("debit", 0)))
#                 credit = Decimal(str(entry.get("credit", 0)))

#                 if account.type == "Asset":

#                     balance = debit - credit

#                     assets.setdefault(account.id, {
#                         "name": account.name,
#                         "code": account.code,
#                         "balance": Decimal("0")
#                     })

#                     assets[account.id]["balance"] += balance
#                     total_assets += balance

#                 elif account.type == "Liability":

#                     balance = credit - debit

#                     liabilities.setdefault(account.id, {
#                         "name": account.name,
#                         "code": account.code,
#                         "balance": Decimal("0")
#                     })

#                     liabilities[account.id]["balance"] += balance
#                     total_liabilities += balance

#                 elif account.type == "Equity":

#                     balance = credit - debit

#                     equity.setdefault(account.id, {
#                         "name": account.name,
#                         "code": account.code,
#                         "balance": Decimal("0")
#                     })

#                     equity[account.id]["balance"] += balance
#                     total_equity += balance

#         return Response({

#             "assets": list(assets.values()),
#             "total_assets": float(total_assets),

#             "liabilities": list(liabilities.values()),
#             "total_liabilities": float(total_liabilities),

#             "equity": list(equity.values()),
#             "total_equity": float(total_equity),

#             "balance_check": float(total_assets - (total_liabilities + total_equity))

#         })




from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from crm.models import ManualJournal, Account


class BalanceSheetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        report_date = request.query_params.get("date")

        if not report_date:
            return Response({"error": "date is required"}, status=400)

        journals = ManualJournal.objects.filter(
            date__lte=report_date,
            status="Posted"
        )

        assets = {}
        liabilities = {}
        equity = {}

        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        total_equity = Decimal("0")

        total_revenue = Decimal("0")
        total_expenses = Decimal("0")

        accounts = {a.id: a for a in Account.objects.all()}

        for journal in journals:

            for entry in journal.entries:

                account = accounts.get(entry["account"])
                if not account:
                    continue

                debit = Decimal(str(entry.get("debit", 0)))
                credit = Decimal(str(entry.get("credit", 0)))

                # Assets
                if account.type == "Asset":

                    balance = debit - credit

                    assets.setdefault(account.id, {
                        "name": account.name,
                        "code": account.code,
                        "balance": Decimal("0")
                    })

                    assets[account.id]["balance"] += balance
                    total_assets += balance

                # Liabilities
                elif account.type == "Liability":

                    balance = credit - debit

                    liabilities.setdefault(account.id, {
                        "name": account.name,
                        "code": account.code,
                        "balance": Decimal("0")
                    })

                    liabilities[account.id]["balance"] += balance
                    total_liabilities += balance

                # Equity
                elif account.type == "Equity":

                    balance = credit - debit

                    equity.setdefault(account.id, {
                        "name": account.name,
                        "code": account.code,
                        "balance": Decimal("0")
                    })

                    equity[account.id]["balance"] += balance
                    total_equity += balance

                # Revenue
                elif account.type == "Revenue":

                    total_revenue += credit - debit

                # Expense
                elif account.type == "Expense":

                    total_expenses += debit - credit


        # Calculate retained earnings
        retained_earnings = total_revenue - total_expenses

        equity["retained"] = {
            "name": "Retained Earnings",
            "code": "RE",
            "balance": retained_earnings
        }

        total_equity += retained_earnings


        return Response({

            "assets": list(assets.values()),
            "total_assets": float(total_assets),

            "liabilities": list(liabilities.values()),
            "total_liabilities": float(total_liabilities),

            "equity": list(equity.values()),
            "total_equity": float(total_equity),

            "balance_check": float(total_assets - (total_liabilities + total_equity))

        })



class StatementOfAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        customer_id = request.query_params.get("customer")

        if not customer_id:
            return Response({"error": "customer id required"}, status=400)

        transactions = []

        balance = Decimal("0")

        # Get invoices
        invoices = Invoice.objects.filter(customer_id=customer_id)

        for inv in invoices:

            amount = Decimal(str(inv.total))

            balance += amount

            transactions.append({
                "date": inv.date,
                "invoice": inv.number,
                "description": "Invoice",
                "debit": float(amount),
                "credit": 0,
                "balance": float(balance)
            })


        # Get Accounts Receivable account
        ar_account = Account.objects.filter(name__icontains="receivable").first()

        # Get payments (journal entries affecting AR)
        journals = ManualJournal.objects.all()

        for j in journals:

            for e in j.entries:

                if e["account"] == ar_account.id:

                    credit = Decimal(str(e.get("credit", 0)))

                    if credit > 0:

                        balance -= credit

                        transactions.append({
                            "date": j.date,
                            "invoice": j.journal_number,
                            "description": "Payment",
                            "debit": 0,
                            "credit": float(credit),
                            "balance": float(balance)
                        })


        # Sort transactions by date
        transactions = sorted(transactions, key=lambda x: x["date"])


        return Response({
            "customer": customer_id,
            "transactions": transactions,
            "total_balance": float(balance)
        })




class VendorStatementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        vendor_id = request.query_params.get("vendor")

        if not vendor_id:
            return Response({"error": "vendor id required"}, status=400)

        vendor_id = int(vendor_id)

        transactions = []
        balance = Decimal("0")

        # ---------------------------
        # Vendor Bills
        # ---------------------------

        bills = ExpenseInvoice.objects.filter(vendor_id=vendor_id)

        for bill in bills:

            amount = Decimal(str(bill.total_amount))

            balance += amount

            transactions.append({
                "date": bill.date,
                "reference": bill.invoice_number,
                "description": "Vendor Bill",
                "debit": 0,
                "credit": float(amount),
                "balance": float(balance)
            })

        # ---------------------------
        # Vendor Payments
        # ---------------------------

        ap_account = Account.objects.filter(code="2010").first()

        journals = ManualJournal.objects.all()

        for j in journals:

            for e in j.entries:

                if e["account"] == ap_account.id:

                    debit = Decimal(str(e.get("debit", 0)))

                    if debit > 0:

                        balance -= debit

                        transactions.append({
                            "date": j.date,
                            "reference": j.journal_number,
                            "description": "Payment",
                            "debit": float(debit),
                            "credit": 0,
                            "balance": float(balance)
                        })

        transactions = sorted(transactions, key=lambda x: x["date"])

        return Response({
            "vendor": vendor_id,
            "transactions": transactions,
            "total_balance": float(balance)
        })



class CashFlowReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        start = request.query_params.get("start")
        end = request.query_params.get("end")

        journals = ManualJournal.objects.filter(
            date__gte=start,
            date__lte=end
        )

        # ----------------------------------
        # Variables
        # ----------------------------------

        revenue = Decimal("0")
        expenses = Decimal("0")
        cogs = Decimal("0")

        ar_change = Decimal("0")
        ap_change = Decimal("0")
        inventory_change = Decimal("0")

        cash_in = Decimal("0")
        cash_out = Decimal("0")

        # ----------------------------------
        # Cash Accounts
        # ----------------------------------

        cash_accounts = Account.objects.filter(code__in=["1010","1020"])
        cash_ids = [a.id for a in cash_accounts]

        # ----------------------------------
        # Calculate Beginning Cash
        # ----------------------------------

        beginning_cash = Decimal("0")

        past_journals = ManualJournal.objects.filter(date__lt=start)

        for j in past_journals:

            for e in j.entries:

                if e["account"] in cash_ids:

                    debit = Decimal(str(e.get("debit",0)))
                    credit = Decimal(str(e.get("credit",0)))

                    beginning_cash += debit
                    beginning_cash -= credit


        # ----------------------------------
        # Process Journals in Period
        # ----------------------------------

        for j in journals:

            for e in j.entries:

                acc = Account.objects.get(id=e["account"])

                debit = Decimal(str(e.get("debit",0)))
                credit = Decimal(str(e.get("credit",0)))

                # Revenue
                if acc.type == "Revenue":
                    revenue += credit

                # Expense
                elif acc.type == "Expense":
                    expenses += debit

                # COGS
                elif acc.code == "5000":
                    cogs += debit

                # Accounts Receivable
                elif acc.code == "1100":
                    ar_change += debit - credit

                # Accounts Payable
                elif acc.code == "2010":
                    ap_change += credit - debit

                # Inventory
                elif acc.code == "1800":
                    inventory_change += debit - credit

                # Cash movements
                if e["account"] in cash_ids:

                    cash_in += debit
                    cash_out += credit


        # ----------------------------------
        # Net Income
        # ----------------------------------

        net_income = revenue - cogs - expenses


        # ----------------------------------
        # Operating Cash Flow
        # ----------------------------------

        operating_cash_flow = (
            net_income
            - ar_change
            + ap_change
            - inventory_change
        )


        # ----------------------------------
        # Net Cash Change
        # ----------------------------------

        net_change = cash_in - cash_out

        ending_cash = beginning_cash + net_change


        # ----------------------------------
        # Response
        # ----------------------------------

        return Response({

            "operating": {
                "net_income": float(net_income),
                "change_ar": float(ar_change),
                "change_inventory": float(inventory_change),
                "change_ap": float(ap_change),
                "operating_cash_flow": float(operating_cash_flow)
            },

            "investing": {
                "cash_flow": 0
            },

            "financing": {
                "cash_flow": 0
            },

            "cash_summary": {
                "beginning_cash": float(beginning_cash),
                "cash_in": float(cash_in),
                "cash_out": float(cash_out),
                "net_change": float(net_change),
                "ending_cash": float(ending_cash)
            }

        })



class TaskCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        payload = request.data

        # =========================
        # VALIDATION
        # =========================

        if not payload.get("title"):
            return Response({
                "error": "Task title is required"
            }, status=400)

        if not payload.get("due_date"):
            return Response({
                "error": "Due date is required"
            }, status=400)

        # =========================
        # ASSIGNED USER
        # =========================

        assigned_user = None
        if payload.get("assigned_to"):
            try:
                assigned_user = User.objects.get(
                    username=payload.get("assigned_to")
                )
            except User.DoesNotExist:
                assigned_user = None

        # =========================
        # CREATE TASK
        # =========================

        task = Task.objects.create(
            title=payload.get("title"),
            description=payload.get("description"),

            due_date=payload.get("due_date"),

            priority=payload.get("priority", "medium"),
            status=payload.get("status", "todo"),

            assigned_to=assigned_user,
            created_by=request.user,

            related_type=payload.get("related_type", "none"),
            related_lead_id=payload.get("related_lead_id"),
            related_customer_id=payload.get("related_customer_id"),
            related_vendor_id=payload.get("related_vendor_id"),

            recurring=payload.get("recurring", False),
            recurrence_pattern=payload.get("recurrence_pattern"),
            next_due_date=payload.get("next_due_date"),

            tags=payload.get("tags", []),
        )

        return Response({
            "success": True,
            "task_id": task.id
        }, status=status.HTTP_201_CREATED)



class TaskListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        tasks = Task.objects.select_related("assigned_to")

        data = []

        for task in tasks:

            data.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,

                "status": task.status,
                "priority": task.priority,

                "due_date": task.due_date,

                "assigned_to": (
                    task.assigned_to.username
                    if task.assigned_to else None
                ),

                "related_type": task.related_type,
                "related_lead_id": task.related_lead_id,
                "related_customer_id": task.related_customer_id,
                "related_vendor_id": task.related_vendor_id,

                "recurring": task.recurring,
                "recurrence_pattern": task.recurrence_pattern,

                "tags": task.tags,

                "created_at": task.created_at,
                "updated_at": task.updated_at
            })

        return Response({
            "success": True,
            "tasks": data
        })


class TaskDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        task = get_object_or_404(
            Task.objects.select_related("assigned_to", "created_by"),
            pk=pk
        )

        today = timezone.now().date()

        # =========================
        # DATE CALCULATIONS
        # =========================

        days_overdue = None
        days_until_due = None
        is_overdue = False

        if task.due_date:
            if task.status != "done" and task.due_date < today:
                is_overdue = True
                days_overdue = (today - task.due_date).days
            else:
                days_until_due = (task.due_date - today).days

        # =========================
        # RELATED OBJECT
        # =========================

        related_info = None

        if task.related_type == "lead" and task.related_lead_id:
            try:
                lead = Lead.objects.get(id=task.related_lead_id)

                related_info = {
                    "type": "lead",
                    "id": lead.id,
                    "name": lead.name,
                    "company": lead.company
                }

            except Lead.DoesNotExist:
                pass

        if task.related_type == "customer" and task.related_customer_id:
            try:
                customer = Customer.objects.get(id=task.related_customer_id)

                related_info = {
                    "type": "customer",
                    "id": customer.id,
                    "name": customer.company_name,
                    "customer_name": customer.customer_name
                }

            except Customer.DoesNotExist:
                pass

        if task.related_type == "vendor" and task.related_vendor_id:
            try:
                vendor = Vendor.objects.get(id=task.related_vendor_id)

                related_info = {
                    "type": "vendor",
                    "id": vendor.id,
                    "name": vendor.company_name,
                    "contact": vendor.contact_person
                }

            except Vendor.DoesNotExist:
                pass



        # =========================
        # RESPONSE
        # =========================

        return Response({

            "id": task.id,
            "title": task.title,
            "description": task.description,

            "status": task.status,
            "status_display": task.get_status_display(),

            "priority": task.priority,
            "priority_display": task.get_priority_display(),

            "due_date": task.due_date,
            "next_due_date": task.next_due_date,

            "recurring": task.recurring,
            "recurrence_pattern": task.recurrence_pattern,

            "assigned_to": {
                "id": task.assigned_to.id,
                "username": task.assigned_to.username
            } if task.assigned_to else None,

            "created_by": {
                "id": task.created_by.id,
                "username": task.created_by.username
            } if task.created_by else None,

            "related_type": task.related_type,
            "related_info": related_info,

            "tags": task.tags,

            "completed_date": task.completed_date,

            "is_overdue": is_overdue,
            "days_overdue": days_overdue,
            "days_until_due": days_until_due,

            "created_at": task.created_at,
            "updated_at": task.updated_at,


        })


class TaskMarkAsDoneView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):

        task = get_object_or_404(Task, pk=pk)

        if task.status == "done":
            return Response({
                "error": "Task is already marked as done"
            }, status=status.HTTP_400_BAD_REQUEST)

        task.status = "done"
        task.completed_date = timezone.now()
        task.save()

        return Response({
            "success": True,
            "message": "Task marked as done",
            "task_id": task.id,
            "status": task.status,
            "completed_date": task.completed_date
        })

class TaskUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):

        task = get_object_or_404(Task, pk=pk)

        payload = request.data

        if "title" in payload:
            task.title = payload["title"]

        if "description" in payload:
            task.description = payload["description"]

        if "due_date" in payload:
            task.due_date = payload["due_date"]

        if "priority" in payload:
            task.priority = payload["priority"]

        if "status" in payload:
            task.status = payload["status"]

        if "tags" in payload:
            task.tags = payload["tags"]

        if "recurring" in payload:
            task.recurring = payload["recurring"]

        if "recurrence_pattern" in payload:
            task.recurrence_pattern = payload["recurrence_pattern"]

        if "next_due_date" in payload:
            task.next_due_date = payload["next_due_date"]

        # assigned user
        if "assigned_to" in payload:

            try:
                user = User.objects.get(username=payload["assigned_to"])
                task.assigned_to = user
            except User.DoesNotExist:
                task.assigned_to = None

        # related entity
        if "related_type" in payload:
            task.related_type = payload["related_type"]

        if "related_lead_id" in payload:
            task.related_lead_id = payload["related_lead_id"]

        if "related_customer_id" in payload:
            task.related_customer_id = payload["related_customer_id"]

        if "related_vendor_id" in payload:
            task.related_vendor_id = payload["related_vendor_id"]

        task.save()

        return Response({
            "success": True,
            "message": "Task updated"
        })


class TaskDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):

        task = get_object_or_404(Task, pk=pk)

        task.delete()

        return Response({
            "success": True,
            "message": "Task deleted"
        })





from datetime import date
class NotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        today = date.today()

        # Ignore completed tasks
        tasks = Task.objects.exclude(status="done")

        notifications = []

        for task in tasks:

            task_date = task.due_date

            # TASK DUE TODAY
            if task_date == today:
                notifications.append({
                    "id": f"due_{task.id}",
                    "type": "due_today",
                    "title": task.title,
                    "priority": task.priority,
                    "due_date": task.due_date,
                    "task_id": task.id
                })
                continue

            # OVERDUE TASK
            if task_date < today:
                notifications.append({
                    "id": f"overdue_{task.id}",
                    "type": "overdue",
                    "title": task.title,
                    "priority": "high",
                    "due_date": task.due_date,
                    "task_id": task.id
                })
                continue

            # RECURRING TASKS
            if task.recurring:

                # WEEKLY
                if task.recurrence_pattern == "weekly":
                    if task_date.weekday() == today.weekday():

                        notifications.append({
                            "id": f"weekly_{task.id}",
                            "type": "recurring_weekly",
                            "title": task.title,
                            "priority": task.priority,
                            "due_date": task.due_date,
                            "task_id": task.id
                        })

                # MONTHLY
                if task.recurrence_pattern == "monthly":
                    if task_date.day == today.day:

                        notifications.append({
                            "id": f"monthly_{task.id}",
                            "type": "recurring_monthly",
                            "title": task.title,
                            "priority": task.priority,
                            "due_date": task.due_date,
                            "task_id": task.id
                        })

        return Response({
            "success": True,
            "count": len(notifications),
            "notifications": notifications
        })

from django.db.models import F
class InventoryNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        notifications = []

        low_stock_items = InventoryItem.objects.filter(
            current_quantity__lte=F("minimum_quantity")
        )

        for item in low_stock_items:
            notifications.append({
                "id": f"inventory_{item.id}",
                "type": "low_stock",
                "title": item.item_name,
                "item_code": item.item_code,
                "current_quantity": float(item.current_quantity),
                "minimum_quantity": float(item.minimum_quantity),
                "priority": "high"
            })

        return Response({
            "success": True,
            "count": len(notifications),
            "notifications": notifications
        })


class CustomerCSVImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file required"}, status=400)

        decoded = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        customers = []

        for row in reader:

            customers.append(
                Customer(
                    company=row.get("company"),
                    contact_name=row.get("contact_name"),
                    email=row.get("email"),
                    phone=row.get("phone"),
                    status=row.get("status"),
                    created_by=request.user,
                )
            )

        Customer.objects.bulk_create(customers)

        return Response({
            "success": True,
            "message": f"{len(customers)} customers imported"
        })



class LeadCSVImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return Response(
                {"error": "CSV file required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        decoded = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        leads = []

        for row in reader:

            leads.append(
                Lead(
                    name=row.get("name"),
                    email=row.get("email"),
                    phone=row.get("phone"),
                    company=row.get("company"),
                    created_by=request.user
                )
            )

        Lead.objects.bulk_create(leads)

        return Response({
            "success": True,
            "message": f"{len(leads)} leads imported"
        })

class VendorCSVImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file required"}, status=400)

        decoded = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        vendors = []

        for row in reader:

            vendors.append(
                Vendor(
                    company=row.get("company"),
                    contact_name=row.get("contact_name"),
                    email=row.get("email"),
                    phone=row.get("phone"),
                    status=row.get("status"),
                    created_by=request.user,
                )
            )

        Vendor.objects.bulk_create(vendors)

        return Response({
            "success": True,
            "message": f"{len(vendors)} vendors imported"
        })

from django.utils.dateparse import parse_date

class InvoiceCSVImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file required"}, status=400)

        decoded = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        created = 0

        for row in reader:

            # ✅ HANDLE CUSTOMER (by name)
            customer = None
            if row.get("customer"):
                customer = Customer.objects.filter(
                    company=row.get("customer")
                ).first()

            # ✅ SAFE PARSE VALUES
            quantity = float(row.get("quantity") or 0)
            price = float(row.get("price") or 0)

            vat_flag = str(row.get("vat_included", "")).lower() == "true"

            # ✅ ITEM STRUCTURE MATCH MODEL
            items = [
                {
                    "name": row.get("item_name") or "",
                    "quantity": quantity,
                    "price": price,
                    "vat_included": vat_flag
                }
            ]

            invoice = Invoice(
                number=row.get("number"),
                customer=customer,
                date=parse_date(row.get("date")) if row.get("date") else None,
                due_date=parse_date(row.get("due_date")) if row.get("due_date") else None,
                status=row.get("status") or "draft",
                items=items,
                created_by=request.user
            )

            # ✅ IMPORTANT: USE SAVE (NOT bulk_create)
            invoice.save()
            created += 1

        return Response({
            "success": True,
            "message": f"{created} invoices imported"
        })










class InventoryCSVImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file required"}, status=400)

        decoded = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        created = 0

        for row in reader:

            item = InventoryItem(
                item_code=row.get("item_code") or "",
                item_name=row.get("item_name") or "",

                category=row.get("category"),
                description=row.get("description"),
                unit_of_measure=row.get("unit_of_measure") or "Unit",

                cost_price=Decimal(row.get("cost_price") or 0),
                selling_price=Decimal(row.get("selling_price") or 0),

                current_quantity=Decimal(row.get("current_quantity") or 0),
                minimum_quantity=Decimal(row.get("minimum_quantity") or 0),

                warehouse=row.get("warehouse"),
                status=row.get("status") or "ACTIVE",

                created_by=request.user
            )

            item.save()
            created += 1

        return Response({
            "success": True,
            "message": f"{created} inventory items imported"
        })





class CompanyWPSCreateView(APIView):

    permission_classes = [IsAuthenticated]

    # ================= GET =================

    def get(self, request):

        company = CompanyWPSProfile.objects.first()

        if not company:
            return Response({
                "profile": None
            })

        return Response({
            "profile": {
                "employer_name": company.employer_name,
                "employer_eid": company.employer_eid,
                "establishment_card_number": company.establishment_card_number,
                "mol_number": company.mol_number,
                "bank_swift_code": company.bank_swift_code,
                "payroll_iban": company.payroll_iban
            }
        })

    # ================= SAVE / UPDATE =================

    def post(self, request):

        employer_name = request.data.get("employer_name")
        employer_eid = request.data.get("employer_eid")
        establishment_card_number = request.data.get("establishment_card_number")
        mol_number = request.data.get("mol_number")
        bank_swift_code = request.data.get("bank_swift_code")
        payroll_iban = request.data.get("payroll_iban")

        company = CompanyWPSProfile.objects.first()

        if company:
            # update existing profile
            company.employer_name = employer_name
            company.employer_eid = employer_eid
            company.establishment_card_number = establishment_card_number
            company.mol_number = mol_number
            company.bank_swift_code = bank_swift_code
            company.payroll_iban = payroll_iban
            company.save()

        else:
            # create new
            company = CompanyWPSProfile.objects.create(
                employer_name=employer_name,
                employer_eid=employer_eid,
                establishment_card_number=establishment_card_number,
                mol_number=mol_number,
                bank_swift_code=bank_swift_code,
                payroll_iban=payroll_iban
            )

        return Response({
            "success": True,
            "company_id": company.id
        })


class EmployeeCreateView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        employee_id = request.data.get("employee_id")
        name = request.data.get("name")
        labour_card_number = request.data.get("labour_card_number")

        bank_swift_code = request.data.get("bank_swift_code")
        bank_account = request.data.get("bank_account")

        basic_salary = Decimal(str(request.data.get("basic_salary")))
        allowances = Decimal(str(request.data.get("allowances", 0)))

        employee = Employee.objects.create(
            employee_id=employee_id,
            name=name,
            labour_card_number=labour_card_number,
            bank_swift_code=bank_swift_code,
            bank_account=bank_account,
            basic_salary=basic_salary,
            allowances=allowances
        )

        return Response({
            "success": True,
            "employee_id": employee.id
        })





class EmployeeListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        employees = Employee.objects.all()

        data = []

        for e in employees:
            data.append({
                "id": e.id,
                "employee_id": e.employee_id,
                "name": e.name,
                "labour_card_number": e.labour_card_number,
                "bank_account": e.bank_account,
                "basic_salary": e.basic_salary,
                "allowances": e.allowances,
                "gross_salary": e.basic_salary + e.allowances
            })

        return Response({
            "success": True,
            "employees": data
        })






class GenerateSIFView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        month = request.data.get("month")
        year = request.data.get("year")
        employees = request.data.get("employees")

        company = CompanyWPSProfile.objects.first()

        today = datetime.today().strftime("%Y%m%d")
        period = f"{year}{month}"

        lines = []
        total_salary = 0

        header = [
            "100",
            company.employer_eid,
            company.employer_name,
            company.bank_swift_code,
            company.payroll_iban,
            period,
            today,
            "REF001",
            str(len(employees)),
            "0"
        ]

        lines.append(",".join(header))

        for emp in employees:

            net = emp["basic_salary"] + emp["allowances"] - emp["deductions"]

            total_salary += net

            row = [
                "200",
                emp["labour_card_number"],
                emp["name"],
                emp["bank_swift_code"],
                emp["bank_account"],
                "M",
                "30",
                str(emp["basic_salary"]),
                str(emp["allowances"]),
                str(emp["deductions"]),
                str(net),
                today
            ]

            lines.append(",".join(row))

        trailer = [
            "300",
            str(len(employees)),
            str(total_salary),
            today
        ]

        lines.append(",".join(trailer))

        sif_content = "\n".join(lines)

        response = HttpResponse(sif_content, content_type="text/plain")

        response["Content-Disposition"] = f'attachment; filename="wps_{period}.sif"'

        return response



class EmployeeDeleteView(APIView):

    permission_classes=[IsAuthenticated]

    def delete(self,request,id):

        employee=Employee.objects.get(id=id)

        employee.delete()

        return Response({"success":True})


class PayrollRunView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        month = request.data.get("month")
        year = request.data.get("year")

        employees = Employee.objects.all()

        data = []

        for emp in employees:

            gross = emp.basic_salary + emp.allowances

            data.append({
                "id": emp.id,
                "employee_id": emp.employee_id,
                "name": emp.name,
                "labour_card_number": emp.labour_card_number,
                "bank_account": emp.bank_account,
                "bank_swift_code": emp.bank_swift_code,
                "basic_salary": emp.basic_salary,
                "allowances": emp.allowances,
                "deductions": 0,
                "gross_salary": gross,
                "net_salary": gross
            })

        return Response({
            "employees": data
        })

class GenerateSIFView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        month = request.data.get("month")
        year = request.data.get("year")
        employees = request.data.get("employees")

        company = CompanyWPSProfile.objects.first()

        today = datetime.today().strftime("%Y%m%d")
        period = f"{year}{month}"

        lines = []
        total_salary = 0

        header = [
            "100",
            company.employer_eid,
            company.employer_name,
            company.bank_swift_code,
            company.payroll_iban,
            period,
            today,
            "REF001",
            str(len(employees)),
            "0"
        ]

        lines.append(",".join(header))

        for emp in employees:

            net = emp["basic_salary"] + emp["allowances"] - emp["deductions"]

            total_salary += net

            row = [
                "200",
                emp["labour_card_number"],
                emp["name"],
                emp["bank_swift_code"],
                emp["bank_account"],
                "M",
                "30",
                str(emp["basic_salary"]),
                str(emp["allowances"]),
                str(emp["deductions"]),
                str(net),
                today
            ]

            lines.append(",".join(row))

        trailer = [
            "300",
            str(len(employees)),
            str(total_salary),
            today
        ]

        lines.append(",".join(trailer))

        sif_content = "\n".join(lines)

        response = HttpResponse(sif_content, content_type="text/plain")

        response["Content-Disposition"] = f'attachment; filename="wps_{period}.sif"'

        return response
    










class BankAccountCreateView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        account = BankAccount.objects.create(
            account_name=request.data.get("account_name"),
            bank_name=request.data.get("bank_name"),
            account_number=request.data.get("account_number"),
            iban=request.data.get("iban"),
            opening_balance=request.data.get("opening_balance")
        )

        return Response({
            "success": True,
            "id": account.id
        })
    



class BankAccountListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        accounts = BankAccount.objects.all()

        data = []

        for acc in accounts:
            data.append({
                "id": acc.id,
                "account_name": acc.account_name,
                "bank_name": acc.bank_name,
                "account_number": acc.account_number,
                "opening_balance": acc.opening_balance
            })

        return Response({
            "accounts": data
        })



import csv

class UploadBankStatementView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        bank_account_id = request.data.get("bank_account_id")
        file = request.FILES.get("file")

        if not bank_account_id:
            return Response({"error": "bank_account_id required"}, status=400)

        if not file:
            return Response({"error": "file required"}, status=400)

        bank_account = BankAccount.objects.get(id=bank_account_id)

        decoded = file.read().decode("utf-8").splitlines()

        reader = csv.DictReader(decoded)

        count = 0

        for row in reader:

            # normalize headers (Date → date etc)
            row = {k.strip().lower(): v.strip() for k, v in row.items()}

            BankStatementTransaction.objects.create(
                bank_account=bank_account,
                date=row.get("date"),
                description=row.get("description"),
                amount=row.get("amount")
            )

            count += 1

        return Response({
            "success": True,
            "transactions_created": count
        })

        


class BankStatementTransactionsView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        bank_account_id = request.query_params.get("bank_account_id")

        transactions = BankStatementTransaction.objects.filter(
            bank_account_id=bank_account_id
        )

        data = []

        for tx in transactions:
            data.append({
                "id": tx.id,
                "date": tx.date,
                "description": tx.description,
                "amount": tx.amount,
                "status": tx.status,
                "matched_reference": tx.matched_reference
            })

        return Response({
            "transactions": data
        })




from decimal import Decimal
from datetime import timedelta
from difflib import SequenceMatcher


class RunBankReconciliationView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        bank_account_id = request.data.get("bank_account_id")

        bank_transactions = BankStatementTransaction.objects.filter(
            bank_account_id=bank_account_id
        )

        ledger_entries = []

        journals = ManualJournal.objects.all()

        # collect ledger entries
        for journal in journals:

            for entry in journal.entries:

                debit = Decimal(str(entry.get("debit", 0)))
                credit = Decimal(str(entry.get("credit", 0)))

                amount = debit - credit

                ledger_entries.append({
                    "amount": amount,
                    "date": journal.date,
                    "description": journal.notes or "",
                    "reference": f"JOURNAL-{journal.journal_number}"
                })

        matched = 0

        for tx in bank_transactions:

            tx.status = "unmatched"
            tx.matched = False
            tx.matched_reference = None

            for ledger in ledger_entries:

                # amount check
                if abs(tx.amount) != abs(ledger["amount"]):
                    continue

                # date check (within 3 days)
                if abs((tx.date - ledger["date"]).days) > 3:
                    continue

                # description similarity
                similarity = SequenceMatcher(
                    None,
                    tx.description.lower(),
                    ledger["description"].lower()
                ).ratio()

                if similarity < 0.6:
                    continue

                # MATCH FOUND
                tx.status = "matched"
                tx.matched = True
                tx.matched_reference = ledger["reference"]

                matched += 1

                break

            tx.save()

        return Response({
            "success": True,
            "matched": matched,
            "total_transactions": bank_transactions.count()
        })






class BankReconciliationSummaryView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        bank_account_id = request.query_params.get("bank_account_id")

        transactions = BankStatementTransaction.objects.filter(
            bank_account_id=bank_account_id
        )

        statement_total = 0

        for tx in transactions:
            statement_total += tx.amount

        return Response({
            "statement_total": statement_total,
            "transactions": transactions.count()
        })




from django.http import FileResponse, Http404
import os

def download_attachment(request, pk):
    try:
        att = ExpenseAttachment.objects.get(id=pk)

        if not os.path.exists(att.file):
            raise Http404("File not found")

        return FileResponse(
            open(att.file, "rb"),
            as_attachment=True,
            filename=att.file_name
        )

    except ExpenseAttachment.DoesNotExist:
        raise Http404("Attachment not found")
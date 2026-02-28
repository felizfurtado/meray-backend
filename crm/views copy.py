class VendorUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        Vendor = get_object_or_404(Vendor, pk=pk)
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

                setattr(Vendor, key, value)

            elif key not in ["notes", "extra_data"]:
                Vendor.extra_data[key] = value

        Vendor.save()

        return Response({
            "success": True,
            "message": "Vendor updated"
        })
 



class VendorAddNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        Vendor = get_object_or_404(Vendor, pk=pk)

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

        notes = Vendor.notes or []
        notes.append(note)

        Vendor.notes = notes   # 🔥 MUST reassign
        Vendor.save()

        return Response(
            {"success": True, "note": note},
            status=status.HTTP_201_CREATED
        )


class VendorDeleteNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, note_id):
        Vendor = get_object_or_404(Vendor, pk=pk)

        notes = Vendor.notes or []
        updated_notes = [n for n in notes if str(n.get("id")) != str(note_id)]

        if len(notes) == len(updated_notes):
            return Response(
                {"error": "Note not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        Vendor.notes = updated_notes
        Vendor.save()

        return Response(
            {"success": True, "message": "Note deleted"},
            status=status.HTTP_200_OK
        )


class VendorDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        Vendor = get_object_or_404(Vendor, pk=pk)
        Vendor.delete()

        return Response(
            {"success": True, "message": "Vendor deleted"},
            status=status.HTTP_200_OK
        )



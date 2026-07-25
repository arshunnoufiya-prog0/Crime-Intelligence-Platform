"""FIR views — paginated list, detail, CRUD, stats. All JsonResponse, no DRF."""
from __future__ import annotations

import json
import datetime
from uuid import UUID
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views import View
from django.utils.decorators import method_decorator

from apps.accounts.decorators import investigator_or_above, super_admin_only, analyst_or_above
from .models import FIR, District, PoliceStation, CaseStatus, CaseCategory, Accused


def fir_to_dict(fir: FIR, detail: bool = False) -> dict:
    data = {
        "id": str(fir.id),
        "fir_id": fir.fir_id,
        "district": fir.district.name,
        "police_station": fir.police_station.name,
        "case_status": fir.case_status,
        "case_category": fir.case_category,
        "crime_head": fir.crime_head,
        "sections": fir.sections,
        "act": fir.act,
        "fir_registration_date": fir.fir_registration_date.isoformat() if fir.fir_registration_date else None,
        "occurrence_date": fir.occurrence_date.isoformat() if fir.occurrence_date else None,
        "occurrence_time": fir.occurrence_time,
        "type_of_information": fir.type_of_information,
        "address": fir.address,
        "latitude": fir.latitude,
        "longitude": fir.longitude,
        "complainant_name": fir.complainant_name,
        "complainant_occupation": fir.complainant_occupation,
        "complainant_address": fir.complainant_address,
        "truth_of_incident": fir.truth_of_incident,
        "gang": fir.gang,
        "alias_group": fir.alias_group,
        "suspected_mastermind": fir.suspected_mastermind,
        "known_associates": fir.known_associates,
        "phone_numbers": fir.phone_numbers,
        "imei_numbers": fir.imei_numbers,
        "bank_accounts": fir.bank_accounts,
        "upi_ids": fir.upi_ids,
        "companies": fir.companies,
        "vehicle_numbers": fir.vehicle_numbers,
        "weapon": fir.weapon,
        "stolen_items": fir.stolen_items,
        "fingerprints_found": fir.fingerprints_found,
        "dna_found": fir.dna_found,
        "cctv_available": fir.cctv_available,
        "crime_pattern_id": fir.crime_pattern_id,
        "linked_firs": fir.linked_firs,
        "confidence_score": fir.confidence_score,
        "is_repeat_offender": fir.is_repeat_offender,
        "predicted_suspect": fir.predicted_suspect,
        "io_name": fir.io_name,
        "io_rank": fir.io_rank,
        "io_police_station": fir.io_police_station,
        "created_at": fir.created_at.isoformat() if fir.created_at else None,
        "updated_at": fir.updated_at.isoformat() if fir.updated_at else None,
    }
    if detail:
        data["accused"] = [{"name": a.name, "identified": a.identified} for a in fir.accused.all()]
    return data


@require_http_methods(["GET"])
@investigator_or_above
def fir_list(request):
    qs = FIR.objects.select_related("district", "police_station").all()

    # INVESTIGATOR scoped to their district
    if request.user.role == "INVESTIGATOR" and request.user.district_id:
        qs = qs.filter(district_id=request.user.district_id)

    # Filters
    if district := request.GET.get("district"):
        qs = qs.filter(district__name__iexact=district)
    if station := request.GET.get("station"):
        qs = qs.filter(police_station__name__iexact=station)
    if status := request.GET.get("status"):
        qs = qs.filter(case_status=status)
    if category := request.GET.get("category"):
        qs = qs.filter(case_category=category)
    if crime_head := request.GET.get("crime_head"):
        qs = qs.filter(crime_head__icontains=crime_head)
    if date_from := request.GET.get("date_from"):
        try:
            qs = qs.filter(fir_registration_date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to := request.GET.get("date_to"):
        try:
            qs = qs.filter(fir_registration_date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass
    if search := request.GET.get("search"):
        qs = qs.filter(
            Q(fir_id__icontains=search) |
            Q(crime_head__icontains=search) |
            Q(address__icontains=search) |
            Q(complainant_name__icontains=search) |
            Q(gang__icontains=search)
        )

    qs = qs.order_by("-fir_registration_date")

    page = int(request.GET.get("page", 1))
    page_size = min(int(request.GET.get("page_size", 20)), 100)
    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    return JsonResponse({
        "results": [fir_to_dict(f) for f in page_obj],
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "total_count": paginator.count,
    })


@require_http_methods(["GET"])
@investigator_or_above
def fir_detail(request, pk: UUID):
    try:
        fir = FIR.objects.select_related("district", "police_station").get(pk=pk)
    except FIR.DoesNotExist:
        return JsonResponse({"error": "FIR not found", "code": "not_found"}, status=404)
    if request.user.role == "INVESTIGATOR" and request.user.district_id != fir.district_id:
        return JsonResponse({"error": "forbidden", "code": "forbidden"}, status=403)
    return JsonResponse(fir_to_dict(fir, detail=True))


@csrf_exempt
@require_http_methods(["POST"])
@investigator_or_above
def fir_create(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)

    try:
        district = District.objects.get(pk=data.get("district_id"))
        station = PoliceStation.objects.get(pk=data.get("police_station_id"))
    except (District.DoesNotExist, PoliceStation.DoesNotExist):
        return JsonResponse({"error": "invalid district or station", "code": "bad_request"}, status=400)

    # INVESTIGATOR can only create in their district
    if request.user.role == "INVESTIGATOR" and request.user.district_id != district.id:
        return JsonResponse({"error": "forbidden", "code": "forbidden"}, status=403)

    fir = FIR.objects.create(
        fir_id=data.get("fir_id", "").strip(),
        district=district,
        police_station=station,
        case_status=data.get("case_status", CaseStatus.UNDER_INVESTIGATION),
        case_category=data.get("case_category", CaseCategory.NON_HEINOUS),
        crime_head=data.get("crime_head", ""),
        sections=data.get("sections", []),
        act=data.get("act", ""),
        fir_registration_date=data.get("fir_registration_date"),
        occurrence_date=data.get("occurrence_date"),
        occurrence_time=data.get("occurrence_time", ""),
        type_of_information=data.get("type_of_information", ""),
        address=data.get("address", ""),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        complainant_name=data.get("complainant_name", ""),
        complainant_occupation=data.get("complainant_occupation", ""),
        complainant_address=data.get("complainant_address", ""),
        truth_of_incident=data.get("truth_of_incident", ""),
        gang=data.get("gang", ""),
        alias_group=data.get("alias_group", ""),
        suspected_mastermind=data.get("suspected_mastermind", ""),
        known_associates=data.get("known_associates", []),
        phone_numbers=data.get("phone_numbers", []),
        imei_numbers=data.get("imei_numbers", []),
        bank_accounts=data.get("bank_accounts", []),
        upi_ids=data.get("upi_ids", []),
        companies=data.get("companies", []),
        vehicle_numbers=data.get("vehicle_numbers", []),
        weapon=data.get("weapon", ""),
        stolen_items=data.get("stolen_items", []),
        fingerprints_found=data.get("fingerprints_found", False),
        dna_found=data.get("dna_found", False),
        cctv_available=data.get("cctv_available", False),
        crime_pattern_id=data.get("crime_pattern_id", ""),
        linked_firs=data.get("linked_firs", []),
        confidence_score=data.get("confidence_score"),
        is_repeat_offender=data.get("is_repeat_offender", False),
        predicted_suspect=data.get("predicted_suspect", ""),
        io_name=data.get("io_name", ""),
        io_rank=data.get("io_rank", ""),
        io_police_station=data.get("io_police_station", ""),
    )
    # Accused
    for a in data.get("accused", []):
        Accused.objects.create(fir=fir, name=a.get("name", ""), identified=a.get("identified", False))
    return JsonResponse(fir_to_dict(fir, detail=True), status=201)


@csrf_exempt
@require_http_methods(["PATCH"])
@investigator_or_above
def fir_update(request, pk: UUID):
    try:
        fir = FIR.objects.get(pk=pk)
    except FIR.DoesNotExist:
        return JsonResponse({"error": "FIR not found", "code": "not_found"}, status=404)
    if request.user.role == "INVESTIGATOR" and request.user.district_id != fir.district_id:
        return JsonResponse({"error": "forbidden", "code": "forbidden"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)

    # Immutable fields
    immutable = ["fir_id", "district", "police_station"]
    for f in immutable:
        data.pop(f, None)

    for field, value in data.items():
        if hasattr(fir, field) and field not in ("id", "created_at", "updated_at"):
            setattr(fir, field, value)
    fir.save()

    if "accused" in data:
        fir.accused.all().delete()
        for a in data["accused"]:
            Accused.objects.create(fir=fir, name=a.get("name", ""), identified=a.get("identified", False))

    return JsonResponse(fir_to_dict(fir, detail=True))


@require_http_methods(["DELETE"])
@super_admin_only
def fir_delete(request, pk: UUID):
    try:
        fir = FIR.objects.get(pk=pk)
    except FIR.DoesNotExist:
        return JsonResponse({"error": "FIR not found", "code": "not_found"}, status=404)
    fir.delete()
    return JsonResponse({"detail": "deleted"})


@require_http_methods(["GET"])
@analyst_or_above
def fir_stats(request):
    qs = FIR.objects.all()
    if request.user.role == "INVESTIGATOR" and request.user.district_id:
        qs = qs.filter(district_id=request.user.district_id)

    total = qs.count()
    by_status = dict(qs.values_list("case_status").annotate(c=Count("id")))
    by_category = dict(qs.values_list("case_category").annotate(c=Count("id")))
    by_crime = dict(qs.values_list("crime_head").annotate(c=Count("id")).order_by("-c")[:10])
    by_month = dict(
        qs.filter(fir_registration_date__isnull=False)
        .extra({"month": "date_trunc('month', fir_registration_date)"})
        .values("month")
        .annotate(c=Count("id"))
        .order_by("month")
    )

    return JsonResponse({
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "by_crime_head": by_crime,
        "by_month": {str(k): v for k, v in by_month.items()},
    })


@require_http_methods(["GET"])
def districts_list(request):
    return JsonResponse([{"id": str(d.id), "name": d.name} for d in District.objects.all()], safe=False)


@require_http_methods(["GET"])
def stations_list(request):
    district_id = request.GET.get("district_id")
    qs = PoliceStation.objects.select_related("district").all()
    if district_id:
        qs = qs.filter(district_id=district_id)
    return JsonResponse([{"id": str(s.id), "name": s.name, "district": s.district.name} for s in qs], safe=False)
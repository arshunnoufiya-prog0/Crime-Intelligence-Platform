"""Management command to import FIR JSON into Django models (idempotent via update_or_create)."""
import json
from django.core.management.base import BaseCommand
from apps.fir.models import FIR, District, PoliceStation, CaseStatus, CaseCategory, Accused


class Command(BaseCommand):
    help = "Import FIR JSON (structure: {\"firs\": [...]}) via update_or_create on (fir_id, police_station)"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to FIR JSON file")

    def handle(self, *args, **options):
        path = options["file"]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        firs = data.get("firs") or data.get("data") or []
        if not isinstance(firs, list):
            self.stderr.write("JSON must contain a top-level 'firs' list")
            return

        total = len(firs)
        created = 0
        updated = 0
        skipped = 0

        for i, rec in enumerate(firs, 1):
            try:
                fm = rec.get("fir_metadata", {}) or {}
                ol = rec.get("occurrence_location", {}) or {}
                od = rec.get("offence_details", {}) or {}
                occd = rec.get("occurrence_details", {}) or {}
                cd = rec.get("complainant_details", {}) or {}
                incd = rec.get("incident_details", {}) or {}
                cn = rec.get("criminal_network", {}) or {}
                de = rec.get("digital_evidence", {}) or {}
                pe = rec.get("physical_evidence", {}) or {}
                ai = rec.get("ai_metadata", {}) or {}
                io = rec.get("investigating_officer", {}) or {}

                fir_id = rec.get("fir_id", "").strip()
                ps_name = fm.get("police_station", "Unknown PS").strip()
                dist_name = fm.get("district", "Bengaluru Urban").strip()

                district, _ = District.objects.get_or_create(name=dist_name)
                police_station, _ = PoliceStation.objects.get_or_create(name=ps_name, defaults={"district": district})
                if police_station.district_id != district.id:
                    police_station.district = district
                    police_station.save()

                defaults = dict(
                    district=district,
                    police_station=police_station,
                    case_status=fm.get("case_status", CaseStatus.UNDER_INVESTIGATION),
                    case_category=fm.get("case_category", CaseCategory.NON_HEINOUS),
                    crime_head=od.get("crime_head", ""),
                    sections=od.get("sections", []),
                    act=od.get("act", ""),
                    fir_registration_date=fm.get("fir_registration_date"),
                    occurrence_date=occd.get("date"),
                    occurrence_time=occd.get("time", ""),
                    type_of_information=occd.get("type_of_information", ""),
                    address=ol.get("address", ""),
                    latitude=ol.get("latitude"),
                    longitude=ol.get("longitude"),
                    complainant_name=cd.get("name", ""),
                    complainant_occupation=cd.get("occupation", ""),
                    complainant_address=cd.get("address", ""),
                    truth_of_incident=incd.get("truth_of_incident", ""),
                    gang=cn.get("gang", ""),
                    alias_group=cn.get("alias_group", ""),
                    suspected_mastermind=cn.get("suspected_mastermind", ""),
                    known_associates=cn.get("known_associates", []),
                    phone_numbers=de.get("phone_numbers", []),
                    imei_numbers=de.get("imei_numbers", []),
                    bank_accounts=de.get("bank_accounts", []),
                    upi_ids=de.get("upi_ids", []),
                    companies=de.get("companies", []),
                    vehicle_numbers=de.get("vehicle_numbers", []),
                    weapon=pe.get("weapon", ""),
                    stolen_items=pe.get("stolen_items", []),
                    fingerprints_found=pe.get("fingerprints_found", False),
                    dna_found=pe.get("dna_found", False),
                    cctv_available=pe.get("cctv_available", False),
                    crime_pattern_id=ai.get("crime_pattern_id", ""),
                    linked_firs=ai.get("linked_firs", []),
                    confidence_score=ai.get("confidence_score"),
                    is_repeat_offender=ai.get("is_repeat_offender", False),
                    predicted_suspect=ai.get("predicted_suspect", ""),
                    io_name=io.get("name", ""),
                    io_rank=io.get("rank", ""),
                    io_police_station=io.get("police_station", ""),
                )

                obj, was_created = FIR.objects.update_or_create(
                    fir_id=fir_id,
                    police_station=police_station,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

                # Accused
                obj.accused.all().delete()
                for a in rec.get("accused_details", []):
                    Accused.objects.create(fir=obj, name=a.get("name", ""), identified=a.get("identified", False))

            except Exception as exc:  # noqa: BLE001
                skipped += 1
                self.stderr.write(f"[{rec.get('fir_id')}] skipped: {exc}")

            if i % 100 == 0 or i == total:
                self.stdout.write(f"Progress: {i}/{total} (created={created}, updated={updated}, skipped={skipped})")

        self.stdout.write(self.style.SUCCESS(
            f"Done: total={total}, created={created}, updated={updated}, skipped={skipped}"
        ))
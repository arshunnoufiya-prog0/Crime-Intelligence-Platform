"""FIR models — District, PoliceStation, CaseStatus/CaseCategory, FIR, Accused."""
from __future__ import annotations

import uuid
from django.db import models
from django.utils import timezone


class District(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fir_district"
        verbose_name_plural = "Districts"

    def __str__(self):
        return self.name


class PoliceStation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="police_stations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fir_policestation"

    def __str__(self):
        return self.name


class CaseStatus(models.TextChoices):
    UNDER_INVESTIGATION = "Under Investigation", "Under Investigation"
    PENDING_TRIAL = "Pending Trial", "Pending Trial"
    DIS_ACQ = "Dis/Acq", "Dis/Acq"
    CLOSED = "Closed", "Closed"


class CaseCategory(models.TextChoices):
    HEINOUS = "Heinous", "Heinous"
    NON_HEINOUS = "Non Heinous", "Non Heinous"


class FIR(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fir_id = models.CharField(max_length=50, db_index=True)  # e.g. "4/2023"
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="firs")
    police_station = models.ForeignKey(PoliceStation, on_delete=models.PROTECT, related_name="firs")

    case_status = models.CharField(max_length=30, choices=CaseStatus.choices, default=CaseStatus.UNDER_INVESTIGATION, db_index=True)
    case_category = models.CharField(max_length=20, choices=CaseCategory.choices, default=CaseCategory.NON_HEINOUS, db_index=True)

    crime_head = models.CharField(max_length=100, db_index=True)
    sections = models.JSONField(default=list, blank=True)  # list of section strings
    act = models.CharField(max_length=200, blank=True, default="")

    fir_registration_date = models.DateField(db_index=True)
    occurrence_date = models.DateField(null=True, blank=True)
    occurrence_time = models.CharField(max_length=50, blank=True, default="")
    type_of_information = models.CharField(max_length=100, blank=True, default="")

    address = models.TextField(blank=True, default="")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    complainant_name = models.CharField(max_length=150, blank=True, default="")
    complainant_occupation = models.CharField(max_length=100, blank=True, default="")
    complainant_address = models.TextField(blank=True, default="")

    truth_of_incident = models.TextField(blank=True, default="")

    # Criminal network
    gang = models.CharField(max_length=150, blank=True, default="")
    alias_group = models.CharField(max_length=150, blank=True, default="")
    suspected_mastermind = models.CharField(max_length=150, blank=True, default="")
    known_associates = models.JSONField(default=list, blank=True)  # list of names

    # Digital evidence
    phone_numbers = models.JSONField(default=list, blank=True)
    imei_numbers = models.JSONField(default=list, blank=True)
    bank_accounts = models.JSONField(default=list, blank=True)
    upi_ids = models.JSONField(default=list, blank=True)
    companies = models.JSONField(default=list, blank=True)
    vehicle_numbers = models.JSONField(default=list, blank=True)

    # Physical evidence
    weapon = models.CharField(max_length=200, blank=True, default="")
    stolen_items = models.JSONField(default=list, blank=True)
    fingerprints_found = models.BooleanField(default=False)
    dna_found = models.BooleanField(default=False)
    cctv_available = models.BooleanField(default=False)

    # AI metadata
    crime_pattern_id = models.CharField(max_length=100, blank=True, default="")
    linked_firs = models.JSONField(default=list, blank=True)  # list of fir_id strings
    confidence_score = models.FloatField(null=True, blank=True)
    is_repeat_offender = models.BooleanField(default=False)
    predicted_suspect = models.CharField(max_length=150, blank=True, default="")

    # Investigating officer
    io_name = models.CharField(max_length=150, blank=True, default="")
    io_rank = models.CharField(max_length=100, blank=True, default="")
    io_police_station = models.CharField(max_length=100, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fir_fir"
        constraints = [
            models.UniqueConstraint(fields=["fir_id", "police_station"], name="unique_fir_per_station"),
        ]
        indexes = [
            models.Index(fields=["district", "case_status"], name="fir_district_status_idx"),
        ]

    def __str__(self):
        return f"{self.fir_id} @ {self.police_station.name}"


class Accused(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fir = models.ForeignKey(FIR, on_delete=models.CASCADE, related_name="accused")
    name = models.CharField(max_length=150)
    identified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fir_accused"

    def __str__(self):
        return self.name
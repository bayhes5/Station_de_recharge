from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.models import (
    Alerte,
    AlertStatus,
    Borne,
    ChargeSessionState,
    DeviceStatus,
    Emplacement,
    EmplacementStatus,
    LockState,
    Reservation,
    ReservationStatus,
    Session,
)


class Command(BaseCommand):
    """Reset one prototype charging bay so a new demo scenario can start."""

    help = (
        "Close open sessions and cancel non-closed reservations on a demo slot. "
        "Use --apply to modify the database."
    )

    def add_arguments(self, parser):
        """Declare command-line arguments."""
        parser.add_argument("--station", default="Station Demo")
        parser.add_argument("--borne", type=int, default=1)
        parser.add_argument("--emplacement", type=int, default=1)
        parser.add_argument(
            "--all-emplacements",
            action="store_true",
            help="Reset every emplacement of the selected borne.",
        )
        parser.add_argument(
            "--keep-future",
            action="store_true",
            help="Keep future reservations and only clear open sessions/current reservations.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write changes. Without it, the command is a dry run.",
        )

    def handle(self, *args, **options):
        """Reset runtime state for the selected station/borne/emplacement."""
        borne = (
            Borne.objects.select_related("station")
            .filter(station__nom=options["station"], numero=options["borne"])
            .first()
        )
        if borne is None:
            raise CommandError(
                f"Borne introuvable: station={options['station']!r}, borne={options['borne']}."
            )

        emplacements = Emplacement.objects.select_related("station", "borne").filter(borne=borne)
        if not options["all_emplacements"]:
            emplacements = emplacements.filter(numero=options["emplacement"])
        emplacements = list(emplacements.order_by("numero"))
        if not emplacements:
            raise CommandError("Aucun emplacement ne correspond aux filtres fournis.")

        now = timezone.now()
        open_sessions = list(
            Session.objects.select_related("reservation", "emplacement")
            .filter(emplacement__in=emplacements, end_time__isnull=True)
            .order_by("start_time")
        )
        reservations = self._reservations_to_clear(
            emplacements=emplacements,
            now=now,
            keep_future=options["keep_future"],
        )

        self._print_summary(
            emplacements=emplacements,
            open_sessions=open_sessions,
            reservations=reservations,
            apply=options["apply"],
            keep_future=options["keep_future"],
        )
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run uniquement. Ajouter --apply pour modifier la base."))
            return

        with transaction.atomic():
            closed_count = self._close_sessions(open_sessions, now)
            cancelled_count = self._cancel_reservations(reservations)
            reset_count = self._reset_emplacements(emplacements)
            resolved_alert_count = self._resolve_session_alerts(open_sessions, now)

        self.stdout.write(
            self.style.SUCCESS(
                "Reset demo terminé: "
                f"sessions_cloturees={closed_count}, "
                f"reservations_annulees={cancelled_count}, "
                f"emplacements_reinitialises={reset_count}, "
                f"alertes_resolues={resolved_alert_count}."
            )
        )

    def _reservations_to_clear(self, *, emplacements, now, keep_future):
        queryset = Reservation.objects.filter(
            emplacement__in=emplacements,
            statut__in=[
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED,
                ReservationStatus.ACTIVE,
            ],
        )
        if keep_future:
            queryset = queryset.filter(date_debut__lte=now)
        return list(queryset.select_related("emplacement").order_by("date_debut"))

    def _print_summary(self, *, emplacements, open_sessions, reservations, apply, keep_future):
        mode = "APPLY" if apply else "DRY-RUN"
        scope = ", ".join(f"{item.borne.nom}/emplacement {item.numero}" for item in emplacements)
        self.stdout.write(f"Mode: {mode}")
        self.stdout.write(f"Cible: {emplacements[0].station.nom} - {scope}")
        self.stdout.write(f"Sessions ouvertes à clôturer: {len(open_sessions)}")
        for session in open_sessions:
            self.stdout.write(
                f"  - {session.id_session} reservation={session.reservation.reference_code} "
                f"state={session.charge_state}"
            )
        reservation_scope = "courantes uniquement" if keep_future else "courantes et futures"
        self.stdout.write(f"Réservations {reservation_scope} à annuler: {len(reservations)}")
        for reservation in reservations:
            self.stdout.write(
                f"  - {reservation.reference_code} statut={reservation.statut} "
                f"debut={reservation.date_debut.isoformat()} fin={reservation.date_fin.isoformat()}"
            )

    def _close_sessions(self, sessions, now):
        closed = 0
        for session in sessions:
            session.end_time = max(now, session.start_time + timedelta(seconds=1))
            session.charge_state = ChargeSessionState.STOPPED
            session.charge_state_updated_at = now
            session.save(update_fields=["end_time", "charge_state", "charge_state_updated_at"])
            if session.reservation.statut != ReservationStatus.COMPLETED:
                session.reservation.statut = ReservationStatus.COMPLETED
                session.reservation.save(update_fields=["statut"])
            closed += 1
        return closed

    def _cancel_reservations(self, reservations):
        cancelled = 0
        for reservation in reservations:
            if reservation.statut == ReservationStatus.COMPLETED:
                continue
            if Session.objects.filter(reservation=reservation).exists():
                continue
            reservation.statut = ReservationStatus.CANCELLED
            reservation.save(update_fields=["statut"])
            cancelled += 1
        return cancelled

    def _reset_emplacements(self, emplacements):
        reset = 0
        for emplacement in emplacements:
            emplacement.statut = EmplacementStatus.AVAILABLE
            emplacement.lock_state = LockState.LOCKED
            emplacement.save(update_fields=["statut", "lock_state"])
            device = getattr(emplacement, "device", None)
            if device and device.status == DeviceStatus.CHARGING:
                device.status = DeviceStatus.ONLINE
                device.last_seen = timezone.now()
                device.save(update_fields=["status", "last_seen"])
            reset += 1
        return reset

    def _resolve_session_alerts(self, sessions, now):
        session_ids = [session.id_session for session in sessions]
        if not session_ids:
            return 0
        return Alerte.objects.filter(session_id__in=session_ids).exclude(
            status__in=["resolue", "resolved", "closed", "fermee"]
        ).update(status=AlertStatus.RESOLVED, resolved_at=now, last_seen=now)

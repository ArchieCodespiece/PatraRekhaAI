import unittest
from datetime import date
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from services.reminders import (
    calculate_reminder_dates,
    generate_reminders_for_deadline,
    find_due_reminders,
)
from services.email_commands import (
    parse_email_command,
    execute_email_command,
)


class RemindersAndCommandsTests(unittest.TestCase):
    def test_reminder_schedule_dates(self):
        target = date(2026, 3, 31)
        schedule = calculate_reminder_dates(target)
        self.assertEqual(schedule["2_days_before"], date(2026, 3, 29))
        self.assertEqual(schedule["1_day_before"], date(2026, 3, 30))
        self.assertEqual(schedule["same_day"], date(2026, 3, 31))

    def test_generate_and_find_due_reminders(self):
        reminders = generate_reminders_for_deadline(
            deadline_iso="2026-03-31",
            event_label="Tender Submission",
            document_id="doc_100",
            document_name="Tender.pdf",
            recipient_email="test@example.com",
        )
        self.assertEqual(len(reminders), 3)

        # On 2026-03-29, 2_days_before is due
        due = find_due_reminders(reminders, current_date=date(2026, 3, 29))
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["reminder_type"], "2_days_before")

    def test_parse_email_commands(self):
        # 1. Remind
        cmd_remind = parse_email_command("Please remind me 2 days before the date.")
        self.assertTrue(cmd_remind["valid"])
        self.assertEqual(cmd_remind["command"], "SET_REMINDER")
        self.assertEqual(cmd_remind["days_before"], 2)

        # 2. What changed
        cmd_diff = parse_email_command("Hi team, what changed?")
        self.assertTrue(cmd_diff["valid"])
        self.assertEqual(cmd_diff["command"], "WHAT_CHANGED")

        # 3. Move deadline
        cmd_move = parse_email_command("Please move the deadline to 15 April 2026.")
        self.assertTrue(cmd_move["valid"])
        self.assertEqual(cmd_move["command"], "MOVE_DEADLINE")
        self.assertEqual(cmd_move["target_date"], "2026-04-15")
        self.assertTrue(cmd_move["requires_confirmation"])

    def test_execute_move_deadline_requires_confirmation(self):
        cmd_move = parse_email_command("move deadline to 2026-04-15")
        res = execute_email_command(cmd_move, context={"deadline": "2026-03-31", "confirmed": False})
        self.assertEqual(res["status"], "AWAITING_CONFIRMATION")

        res_confirmed = execute_email_command(cmd_move, context={"deadline": "2026-03-31", "confirmed": True})
        self.assertEqual(res_confirmed["status"], "SUCCESS")
        self.assertEqual(res_confirmed["new_deadline"], "2026-04-15")


if __name__ == "__main__":
    unittest.main()

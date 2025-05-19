import sqlite3
import datetime
import tempfile

from semafor.models import Project
from semafor.models import ProjectAlias
from semafor.models import MissingProjectAlias
from semafor.models import WorkAssessment
from semafor.models import OutOfBoundsException


# This class handles files coming from the following mobile APP:
# https://play.google.com/store/apps/details?id=org.transversalcoop.control_horari
class ControlHorari:
    TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
    MIX_HOURS_NAME = "Popurri"
    STRUCTURAL_NAME = "Estructural: altres"

    def __init__(self, dbfile):
        self.db = sqlite3.connect(dbfile)
        self.cur = self.db.cursor()

    def get_projects_worked_time(self):
        self.discard_dangling_checks()
        self.get_check_types_names()

        all_projects = {}
        # TODO do all months demanded by user or all months in file
        for year in range(2023, 2026):
            for i in range(1, 13):
                projects = self.get_month_projects_worked_time(f"{year}-{i:02}")
                for k, v in projects.items():
                    all_projects.setdefault(k, []).append(
                        {
                            "year": year,
                            "month": i,
                            "worked_time": v,
                        }
                    )

        return all_projects

    def discard_dangling_checks(self):
        sql = "SELECT check_type_id FROM checks ORDER BY timestamp DESC LIMIT 1;"
        self.cur.execute(sql)
        while self.cur.fetchone()[0] is not None:
            self.cur.execute("DELETE FROM checks ORDER BY timestamp DESC LIMIT 1;")
            self.cur.execute(sql)

    def get_check_types_names(self):
        self.check_types = {}
        for row in self.cur.execute("SELECT id, name FROM check_types;"):
            id, name = row
            self.check_types[id] = name

    def get_month_projects_worked_time(self, date_str):
        sql = """SELECT timestamp, check_type_id, multiplier FROM checks
                 WHERE timestamp LIKE ? ORDER BY timestamp ASC;"""
        lst = []
        try:
            for row in self.cur.execute(sql, [date_str + "-%"]):
                lst.append(
                    (
                        datetime.datetime.strptime(row[0], self.TIME_FORMAT),
                        row[1],
                        row[2],
                    )
                )
        except Exception:
            sql = """SELECT timestamp, check_type_id FROM checks
                     WHERE timestamp LIKE ? ORDER BY timestamp ASC;"""
            for row in self.cur.execute(sql, [date_str + "-%"]):
                lst.append(
                    (datetime.datetime.strptime(row[0], self.TIME_FORMAT), row[1], 100)
                )

        projects = {}
        for i in range(len(lst) - 1):
            s, e = lst[i], lst[i + 1]
            if s[1]:
                k = self.check_types[s[1]].strip()
                if k in projects.keys():
                    projects[k] += (e[0] - s[0]) * s[2] / 100
                else:
                    projects[k] = (e[0] - s[0]) * s[2] / 100

        return self.distribute_mix_hours(projects)

    def distribute_mix_hours(self, projects):
        total, mix_time = datetime.timedelta(), datetime.timedelta()
        for key in projects.keys():
            if key == self.MIX_HOURS_NAME:
                mix_time = projects[key]
            total += projects[key]

        if mix_time == datetime.timedelta():
            return projects
        if mix_time == total:  # if all is mix, we assume Estructural
            return {self.STRUCTURAL_NAME: total}

        mix_fraction = mix_time / total
        multiplier = 1 / (1 - mix_fraction)
        new_projects = {}
        for key in projects.keys():
            if key != self.MIX_HOURS_NAME:
                new_projects[key] = projects[key] * multiplier

        return new_projects


def update_worker_assessments(request, worker):
    with tempfile.NamedTemporaryFile(delete_on_close=False) as fp:
        fp.write(request.FILES["checks_file"].read())
        fp.close()

        return update_worker_assessments_aux(worker, fp.name)


def update_worker_assessments_aux(worker, dbfile):
    WorkAssessment.objects.filter(worker=worker).delete()
    projects = ControlHorari(dbfile).get_projects_worked_time()
    db_projects, missing_projects = {}, set()
    for k in projects:
        try:
            project = Project.objects.get(name=k)
            db_projects[k] = project
        except Project.DoesNotExist:
            try:
                alias = ProjectAlias.objects.get(alias=k, worker=worker)
                db_projects[k] = alias.project
            except ProjectAlias.DoesNotExist:
                missing_projects.add(k)

    errors = []
    if len(missing_projects) == 0:
        for pname, assessments in projects.items():
            project = db_projects[pname]
            for assessment in assessments:
                year = assessment["year"]
                month = assessment["month"]
                try:
                    obj, created = WorkAssessment.objects.get_or_create(
                        worker=worker,
                        project=project,
                        year=year,
                        month=month,
                        defaults={"assessment": assessment["worked_time"]},
                    )
                    if not created:
                        obj.assessment += assessment["worked_time"]
                        obj.save()
                except OutOfBoundsException as ex:
                    errors.append(f"{project.name} ({year}-{month:02}): {ex}")
    else:
        for p in missing_projects:
            MissingProjectAlias.objects.get_or_create(worker=worker, alias=p)

    return missing_projects, errors

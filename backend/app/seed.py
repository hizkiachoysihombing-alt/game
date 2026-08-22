"""Seed the minimum electrical engineering learning flow for local development."""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.models import (
    User, UserRole, Subject, Course, Module, Lesson, Topic, QuestionBank,
    Question, QuestionType, QuestionDifficulty, QuestionWorkflowStatus, QuestionAnswer,
    Achievement, Quest, UserQuest,
)
from app.content.electrical_engineering_curriculum import COURSE_METADATA, CURRICULUM, STARTER_QUESTIONS


def slugify(value: str) -> str:
    return value.lower().replace("'", "").replace("/", " ").replace("-", " ").replace("  ", " ").replace(" ", "-")


def seed() -> None:
    db = SessionLocal()
    try:
        # Subjects removed from the active technical curriculum remain in the
        # database for referential integrity, but are hidden from Journey.
        db.query(Subject).update({Subject.order: 900}, synchronize_session=False)
        subjects_by_slug = {}
        topics_by_key = {}
        for order, (name, slug, topic_names) in enumerate(CURRICULUM, start=1):
            metadata = COURSE_METADATA.get(slug, {})
            curriculum_subject = db.query(Subject).filter(Subject.slug == slug).first()
            if curriculum_subject is None:
                curriculum_subject = Subject(name=name, slug=slug, description=f"Adaptive ElectroQuest journey for {name}.", icon="zap", order=order, curriculum_code=metadata.get("code"), semester=metadata.get("semester"), credits=metadata.get("credits"))
                db.add(curriculum_subject)
                db.flush()
            else:
                curriculum_subject.name = name
                curriculum_subject.order = order
                curriculum_subject.curriculum_code = metadata.get("code")
                curriculum_subject.semester = metadata.get("semester")
                curriculum_subject.credits = metadata.get("credits")
            subjects_by_slug[slug] = curriculum_subject
            for topic_name in topic_names:
                topic_slug = slugify(topic_name)
                curriculum_topic = db.query(Topic).filter(Topic.subject_id == curriculum_subject.id, Topic.slug == topic_slug).first()
                if curriculum_topic is None:
                    curriculum_topic = Topic(subject_id=curriculum_subject.id, name=topic_name, slug=topic_slug, description=f"Master {topic_name} through adaptive practice.")
                    db.add(curriculum_topic)
                    db.flush()
                topics_by_key[(slug, topic_name)] = curriculum_topic

        for subject_slug, topic_name, title, prompt, expected, units, tolerance, difficulty in STARTER_QUESTIONS:
            starter_topic = topics_by_key[(subject_slug, topic_name)]
            starter_bank = db.query(QuestionBank).filter(QuestionBank.topic_id == starter_topic.id, QuestionBank.name == "ElectroQuest Adaptive Bank").first()
            if starter_bank is None:
                starter_bank = QuestionBank(topic_id=starter_topic.id, name="ElectroQuest Adaptive Bank", description="Original, validated starter problems for adaptive practice.")
                db.add(starter_bank)
                db.flush()
            if db.query(Question).filter(Question.question_bank_id == starter_bank.id, Question.title == title).first() is None:
                db.add(Question(question_bank_id=starter_bank.id, title=title, description="Original ElectroQuest numerical problem.", question_type=QuestionType.NUMERICAL, difficulty=QuestionDifficulty(difficulty), content_html=f"<p>{prompt}</p>", solution_html=f"<p>Expected result: {expected}</p>", explanation="Check the governing equation, substitute SI quantities, and verify the unit.", expected_answer=expected, numerical_tolerance=tolerance, accepted_units=units, xp_reward=10 if difficulty == "easy" else 20, bloom_level="apply", is_published=True, workflow_status=QuestionWorkflowStatus.PUBLISHED.value, requires_citation=False))

        # Deterministic warm-up generators provide twenty distinct easy variants per
        # Engineering Mathematics section. The same generator contract can be
        # extended to every engineering subject without changing the Journey UI.
        math_variants = {
            "Algebra and equations": [
                (f"Algebra Warm-up {i:02d}", f"Solve {a}x + {b} = {a * x + b}.", str(x))
                for i in range(1, 21)
                for a, b, x in [(2 + i % 5, 1 + i % 7, 1 + i)]
            ],
            "Complex numbers": [
                (f"Complex Numbers Warm-up {i:02d}", f"Find the magnitude of {3 * scale} + j{4 * scale}.", str(5 * scale))
                for i in range(1, 21)
                for scale in [i]
            ],
            "Differential equations": [
                (f"Differentiation Warm-up {i:02d}", f"For y = {coefficient}x^2, find dy/dx at x = {point}.", str(2 * coefficient * point))
                for i in range(1, 21)
                for coefficient, point in [(1 + i % 6, 1 + i % 5)]
            ],
            "Matrices and numerical methods": [
                (f"Matrix Warm-up {i:02d}", f"Find the determinant of [[{a}, {b}], [{c}, {d}]].", str(a * d - b * c))
                for i in range(1, 21)
                for a, b, c, d in [(1 + i % 5, i % 3, 1 + i % 4, 2 + i % 6)]
            ],
        }
        for topic_name, variants in math_variants.items():
            math_topic = topics_by_key[("engineering-mathematics", topic_name)]
            math_bank = db.query(QuestionBank).filter(QuestionBank.topic_id == math_topic.id, QuestionBank.name == "ElectroQuest Warm-up Generator").first()
            if math_bank is None:
                math_bank = QuestionBank(topic_id=math_topic.id, name="ElectroQuest Warm-up Generator", description="Twenty original easy variants for a full unit run.")
                db.add(math_bank)
                db.flush()
            for title, prompt, expected in variants:
                if db.query(Question).filter(Question.question_bank_id == math_bank.id, Question.title == title).first() is None:
                    db.add(Question(question_bank_id=math_bank.id, title=title, description="Generated warm-up variant.", question_type=QuestionType.NUMERICAL, difficulty=QuestionDifficulty.EASY, content_html=f"<p>{prompt}</p>", solution_html=f"<p>Expected result: {expected}</p>", explanation="Apply the section method carefully and verify the arithmetic.", expected_answer=expected, numerical_tolerance=0.001, accepted_units=[], xp_reward=10, bloom_level="apply", is_published=True, workflow_status=QuestionWorkflowStatus.PUBLISHED.value, requires_citation=False))

        # Pre-engineering foundations: every section receives a complete 20-item
        # warm-up pool so a new learner never starts with engineering mathematics.
        foundation_generators = {
            ("basic-mathematics", "Arithmetic and fractions"): lambda i: (f"Arithmetic {i:02d}", f"Calculate {3*i} + {2*i} - {i}.", str(4*i), []),
            ("basic-mathematics", "Algebra foundations"): lambda i: (f"Basic Algebra {i:02d}", f"Solve {2+i%4}x + {i} = {(2+i%4)*(i+2)+i}.", str(i+2), []),
            ("basic-mathematics", "Geometry and trigonometry"): lambda i: (f"Rectangle Area {i:02d}", f"Find the area of a rectangle {i+2} m by {i%6+2} m.", str((i+2)*(i%6+2)), ["m2"]),
            ("basic-mathematics", "Functions and graphs"): lambda i: (f"Function Value {i:02d}", f"For f(x) = {i%5+2}x + {i}, find f({i%4+1}).", str((i%5+2)*(i%4+1)+i), []),
            ("basic-physics", "Units and measurement"): lambda i: (f"Unit Conversion {i:02d}", f"Convert {i+1} kilometres to metres.", str((i+1)*1000), ["m"]),
            ("basic-physics", "Motion and force"): lambda i: (f"Uniform Motion {i:02d}", f"An object moves at {i+2} m/s for {i%5+2} s. Find its distance.", str((i+2)*(i%5+2)), ["m"]),
            ("basic-physics", "Work energy and power"): lambda i: (f"Mechanical Work {i:02d}", f"A force of {i+5} N moves an object {i%4+2} m. Find the work in joules.", str((i+5)*(i%4+2)), []),
            ("basic-physics", "Waves and basic electricity"): lambda i: (f"Wave Speed {i:02d}", f"A wave has frequency {i+2} Hz and wavelength {i%5+1} m. Find its speed.", str((i+2)*(i%5+1)), []),
        }
        for key, generator in foundation_generators.items():
            foundation_topic = topics_by_key[key]
            bank = db.query(QuestionBank).filter_by(topic_id=foundation_topic.id, name="Foundation Warm-up Bank").first()
            if bank is None:
                bank = QuestionBank(topic_id=foundation_topic.id, name="Foundation Warm-up Bank", description="Twenty introductory variants for new learners.")
                db.add(bank); db.flush()
            for i in range(1, 21):
                title, prompt, expected, units = generator(i)
                if db.query(Question).filter_by(question_bank_id=bank.id, title=title).first() is None:
                    db.add(Question(question_bank_id=bank.id, title=title, question_type=QuestionType.NUMERICAL, difficulty=QuestionDifficulty.EASY, content_html=f"<p>{prompt}</p>", explanation="Use the basic relationship shown in the question and check the unit.", expected_answer=expected, numerical_tolerance=0.001, accepted_units=units, xp_reward=10, bloom_level="apply", is_published=True, workflow_status=QuestionWorkflowStatus.PUBLISHED.value, requires_citation=False))
                elif key == ("basic-physics", "Work energy and power"):
                    existing = db.query(Question).filter_by(question_bank_id=bank.id, title=title).first()
                    existing.content_html = f"<p>{prompt}</p>"
                    existing.accepted_units = []

        # Interactive programming pools. These checks inspect source structure;
        # submitted code is never evaluated inside the API process.
        coding_topics = {
            ("procedural-programming", "Variables and input output"): ("python", "value = 0\n# Print the value below\n", ["print("], "Store the number {n} in a variable and print it."),
            ("procedural-programming", "Conditions and loops"): ("python", "limit = {n}\n# Write your loop below\n", ["for ", "range("], "Use a for loop and range to print the numbers from 1 through {n}."),
            ("procedural-programming", "Functions"): ("python", "def calculate(value):\n    # Return twice the value\n    pass\n", ["def calculate", "return"], "Complete calculate(value) so it returns twice its input. Use {n} as a sample input."),
            ("procedural-programming", "Arrays and strings"): ("python", "values = list(range(1, {n}))\n# Print the total\n", ["sum(", "print("], "Use sum and print to display the total of values."),
            ("object-oriented-programming", "Classes and objects"): ("python", "# Define Sensor and create one object\n", ["class sensor", "sensor("], "Define a Sensor class and create an instance named sensor_{n}."),
            ("object-oriented-programming", "Encapsulation"): ("python", "class Counter:\n    def __init__(self):\n        self._value = 0\n", ["def increment", "self._value"], "Add an increment method to Counter while keeping its value encapsulated."),
            ("object-oriented-programming", "Inheritance and polymorphism"): ("python", "class Device:\n    def status(self):\n        return 'ready'\n", ["class sensor(device)", "def status"], "Create Sensor as a Device subclass and override status()."),
            ("object-oriented-programming", "Interfaces and composition"): ("python", "class Battery:\n    def level(self):\n        return {n}\n", ["class device", "def __init__", "battery"], "Create a Device that receives and stores a Battery through its constructor."),
            ("data-structures-algorithms", "Linear data structures"): ("python", "items = list(range({n}))\n", ["append("], "Append one new item to items."),
            ("data-structures-algorithms", "Searching and sorting"): ("python", "values = [{n}, 3, 1, 2]\n", ["sorted("], "Create a sorted version of values using sorted()."),
            ("data-structures-algorithms", "Recursion"): ("python", "def countdown(n):\n    # Add base case and recursion\n    pass\n", ["if ", "countdown("], "Complete countdown with a base case and a recursive call."),
            ("data-structures-algorithms", "Algorithm complexity"): ("python", "values = list(range({n}))\n", ["for "], "Visit each value exactly once using a loop."),
        }
        for key, (language, starter, required, prompt) in coding_topics.items():
            code_topic = topics_by_key[key]
            bank = db.query(QuestionBank).filter_by(topic_id=code_topic.id, name="Interactive Coding Lab").first()
            if bank is None:
                bank = QuestionBank(topic_id=code_topic.id, name="Interactive Coding Lab", description="Twenty safe source-validated coding challenges.")
                db.add(bank); db.flush()
            for i in range(1, 21):
                title = f"Coding Lab {i:02d}"
                if db.query(Question).filter_by(question_bank_id=bank.id, title=title).first() is None:
                    db.add(Question(question_bank_id=bank.id, title=title, description="Interactive programming exercise.", question_type=QuestionType.SHORT_ANSWER, difficulty=QuestionDifficulty.EASY if i <= 10 else QuestionDifficulty.MEDIUM, content_html=f"<p>{prompt.format(n=i+2)}</p><p>Your solution is checked against {len(required)} code requirements.</p>", explanation="All declared code requirements passed.", coding_language=language, starter_code=starter.format(n=i+2), test_cases=[{"name": f"Uses {token.strip()}", "required": [token], "forbidden": ["eval(", "exec(", "__import__"]} for token in required], xp_reward=15 if i <= 10 else 20, bloom_level="create", is_published=True, workflow_status=QuestionWorkflowStatus.PUBLISHED.value, requires_citation=False))

        # Networking begins with conceptual and subnet arithmetic practice.
        network_questions = {
            "Network fundamentals": [("Network Device", "Which device forwards packets between different IP networks?", "router")],
            "OSI and TCP-IP": [("Transport Protocol", "Which reliable transport protocol uses a connection-oriented service?", "tcp")],
            "IPv4 addressing and subnetting": [("IPv4 Host Count", "How many usable host addresses are available in a /{prefix} IPv4 subnet?", None)],
            "Routing and network services": [("Name Resolution", "Which network service resolves domain names to IP addresses?", "dns")],
        }
        for topic_name, templates in network_questions.items():
            network_topic = topics_by_key[("computer-networks", topic_name)]
            bank = db.query(QuestionBank).filter_by(topic_id=network_topic.id, name="Networking Practice Bank").first()
            if bank is None:
                bank = QuestionBank(topic_id=network_topic.id, name="Networking Practice Bank", description="Core networking and subnetting practice.")
                db.add(bank); db.flush()
            for i in range(1, 21):
                title, prompt, fixed = templates[0]; prefix = 24 + (i % 5)
                expected = fixed or str((2 ** (32-prefix))-2)
                item_title = f"{title} {i:02d}"
                if db.query(Question).filter_by(question_bank_id=bank.id, title=item_title).first() is None:
                    db.add(Question(question_bank_id=bank.id, title=item_title, question_type=QuestionType.NUMERICAL if fixed is None else QuestionType.SHORT_ANSWER, difficulty=QuestionDifficulty.EASY, content_html=f"<p>{prompt.format(prefix=prefix)}</p>", explanation="Review the protocol layer or subnet host-bit calculation.", expected_answer=expected, numerical_tolerance=0, accepted_units=[], xp_reward=10, is_published=True, workflow_status=QuestionWorkflowStatus.PUBLISHED.value, requires_citation=False))

        instructor = db.query(User).filter(User.username == "demo-instructor").first()
        if instructor is None:
            instructor = User(email="instructor@electroquest.local", username="demo-instructor", full_name="ElectroQuest Instructor", hashed_password=hash_password("DemoInstructor123!"), role=UserRole.INSTRUCTOR, is_active=True, is_verified=True)
            db.add(instructor)
            db.flush()

        # Every curriculum subject is also available as a structured course. Journey
        # remains mixed and adaptive, while Library offers a focused reference path.
        for order, (subject_name, subject_slug, topic_names) in enumerate(CURRICULUM, start=1):
            curriculum_subject = subjects_by_slug[subject_slug]
            course_slug = f"{subject_slug}-essentials"
            curriculum_course = db.query(Course).filter(Course.slug == course_slug).first()
            tier = "beginner" if order <= 10 else "intermediate" if order <= 22 else "advanced"
            if curriculum_course is None:
                curriculum_course = Course(
                    subject_id=curriculum_subject.id,
                    instructor_id=instructor.id,
                    name=f"{subject_name} Essentials",
                    slug=course_slug,
                    description=f"Build practical {subject_name.lower()} skills through concise concepts, worked methods, and adaptive practice.",
                    difficulty=tier,
                    estimated_hours=max(4, len(topic_names) * 2),
                    order=order,
                    is_published=True,
                )
                db.add(curriculum_course)
                db.flush()
            else:
                curriculum_course.is_published = True
                curriculum_course.order = order

            for module_order, topic_name in enumerate(topic_names, start=1):
                curriculum_module = db.query(Module).filter(Module.course_id == curriculum_course.id, Module.order == module_order).first()
                if curriculum_module is None:
                    curriculum_module = Module(course_id=curriculum_course.id, name=topic_name, order=module_order)
                    db.add(curriculum_module)
                    db.flush()
                curriculum_lesson = db.query(Lesson).filter(Lesson.module_id == curriculum_module.id, Lesson.order == 1).first()
                if curriculum_lesson is None:
                    curriculum_lesson = Lesson(
                        module_id=curriculum_module.id,
                        name=f"Understanding {topic_name}",
                        content_html=(
                            f"<h2>{topic_name}</h2>"
                            f"<p>This lesson introduces the governing ideas and engineering vocabulary used in {topic_name}.</p>"
                            "<h3>Learning workflow</h3><ol><li>Identify known quantities and assumptions.</li>"
                            "<li>Select the governing principle or model.</li><li>Solve using consistent SI units.</li>"
                            "<li>Check whether the result is physically reasonable.</li></ol>"
                            "<p>Continue in Journey for adaptive numerical practice and mastery measurement.</p>"
                        ),
                        order=1,
                        is_published=True,
                    )
                    db.add(curriculum_lesson)

        subject = db.query(Subject).filter(Subject.slug == "circuit-analysis").first()
        if subject is None:
            subject = Subject(name="Circuit Analysis", slug="circuit-analysis", description="Foundations of voltage, current, resistance, and circuit laws.", icon="circuit", order=1)
            db.add(subject)
            db.flush()

        course = db.query(Course).filter(Course.slug == "circuit-analysis-foundations").first()
        if course is None:
            course = Course(subject_id=subject.id, instructor_id=instructor.id, name="Circuit Analysis Foundations", slug="circuit-analysis-foundations", description="Learn Ohm's law and solve your first circuit problems.", difficulty="beginner", estimated_hours=4, order=1, is_published=True)
            db.add(course)
            db.flush()

        module = db.query(Module).filter(Module.course_id == course.id, Module.order == 1).first()
        if module is None:
            module = Module(course_id=course.id, name="Ohm's Law", order=1)
            db.add(module)
            db.flush()

        lesson = db.query(Lesson).filter(Lesson.module_id == module.id, Lesson.order == 1).first()
        if lesson is None:
            lesson = Lesson(module_id=module.id, name="Voltage, current, and resistance", content_html="<h2>Ohm's Law</h2><p>Voltage equals current multiplied by resistance: V = I * R.</p><p>Use consistent units and show your working.</p>", order=1, is_published=True)
            db.add(lesson)

        topic = db.query(Topic).filter(Topic.subject_id == subject.id, Topic.slug == "ohms-law").first()
        if topic is None:
            topic = Topic(subject_id=subject.id, name="Ohm's Law", slug="ohms-law", description="The relationship between voltage, current, and resistance.")
            db.add(topic)
            db.flush()

        bank = db.query(QuestionBank).filter(QuestionBank.topic_id == topic.id).first()
        if bank is None:
            bank = QuestionBank(topic_id=topic.id, name="Ohm's Law Practice", description="Introductory calculation problems.")
            db.add(bank)
            db.flush()

        question = db.query(Question).filter(Question.question_bank_id == bank.id).first()
        if question is None:
            question = Question(question_bank_id=bank.id, title="Calculate the current", description="Use Ohm's law.", question_type=QuestionType.NUMERICAL, difficulty=QuestionDifficulty.EASY, content_html="<p>A 12 V source is connected across a 6 ohm resistor. What current flows?</p>", solution_html="<p>I = V / R = 12 / 6 = 2 A.</p>", explanation="Current is voltage divided by resistance.", expected_answer="2", numerical_tolerance=0.01, accepted_units=["A"], xp_reward=10, is_published=True, workflow_status=QuestionWorkflowStatus.PUBLISHED.value, requires_citation=False)
            db.add(question)
            db.flush()

        achievements = [
            ("First Current", "first-current", "Solve your first engineering problem.", "common", 10, 5, {"field": "problems_solved", "target": 1}),
            ("Circuit Apprentice", "circuit-apprentice", "Solve five engineering problems.", "rare", 25, 15, {"field": "problems_solved", "target": 5}),
            ("Century of Learning", "century-xp", "Earn 100 XP.", "rare", 20, 20, {"field": "total_xp", "target": 100}),
        ]
        for name, slug, description, rarity, xp_reward, coin_reward, criteria in achievements:
            if db.query(Achievement).filter_by(slug=slug).first() is None:
                db.add(Achievement(name=name, slug=slug, description=description, rarity=rarity, xp_reward=xp_reward, coin_reward=coin_reward, criteria=criteria))

        daily = db.query(Quest).filter(Quest.name == "Daily Circuit Practice").first()
        if daily is None:
            daily = Quest(name="Daily Circuit Practice", description="Submit one engineering problem today.", quest_type="daily", criteria={"event": "problem_submitted"}, xp_reward=15, coin_reward=5, difficulty="easy")
            db.add(daily)
            db.flush()
        for student in db.query(User).filter(User.role == UserRole.STUDENT).all():
            if db.query(UserQuest).filter_by(user_id=student.id, quest_id=daily.id).first() is None:
                db.add(UserQuest(user_id=student.id, quest_id=daily.id, target=1))

        db.commit()
        print("ElectroQuest seed data is ready")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

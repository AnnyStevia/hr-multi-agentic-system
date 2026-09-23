from sqlalchemy.orm import Session, joinedload

from app.modules.training.models import OnboardingTraining, Training


class TrainingRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_trainings(self) -> list[Training]:
        return self.db.query(Training).order_by(Training.title.asc(), Training.id.asc()).all()

    def get_training(self, training_id: int) -> Training | None:
        return self.db.query(Training).filter(Training.id == training_id).first()

    def add_training(self, training: Training) -> Training:
        self.db.add(training)
        self.db.commit()
        self.db.refresh(training)
        return training

    def save_training(self, training: Training) -> Training:
        self.db.commit()
        self.db.refresh(training)
        return training

    def delete_training(self, training: Training) -> None:
        self.db.delete(training)
        self.db.commit()

    def list_assignments(self, onboarding_id: int) -> list[OnboardingTraining]:
        return (
            self.db.query(OnboardingTraining)
            .options(joinedload(OnboardingTraining.training))
            .filter(OnboardingTraining.onboarding_id == onboarding_id)
            .order_by(OnboardingTraining.assigned_at.desc(), OnboardingTraining.id.desc())
            .all()
        )

    def get_assignment(self, assignment_id: int) -> OnboardingTraining | None:
        return (
            self.db.query(OnboardingTraining)
            .options(joinedload(OnboardingTraining.training))
            .filter(OnboardingTraining.id == assignment_id)
            .first()
        )

    def get_assignment_for_onboarding(
        self, assignment_id: int, onboarding_id: int
    ) -> OnboardingTraining | None:
        return (
            self.db.query(OnboardingTraining)
            .options(joinedload(OnboardingTraining.training))
            .filter(
                OnboardingTraining.id == assignment_id,
                OnboardingTraining.onboarding_id == onboarding_id,
            )
            .first()
        )

    def find_assignment(self, onboarding_id: int, training_id: int) -> OnboardingTraining | None:
        return (
            self.db.query(OnboardingTraining)
            .filter(
                OnboardingTraining.onboarding_id == onboarding_id,
                OnboardingTraining.training_id == training_id,
            )
            .first()
        )

    def add_assignment(
        self, assignment: OnboardingTraining, *, commit: bool = True
    ) -> OnboardingTraining:
        self.db.add(assignment)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(assignment)
        return (
            self.db.query(OnboardingTraining)
            .options(joinedload(OnboardingTraining.training))
            .filter(OnboardingTraining.id == assignment.id)
            .one()
        )

    def save_assignment(self, assignment: OnboardingTraining) -> OnboardingTraining:
        self.db.commit()
        self.db.refresh(assignment)
        return (
            self.db.query(OnboardingTraining)
            .options(joinedload(OnboardingTraining.training))
            .filter(OnboardingTraining.id == assignment.id)
            .one()
        )

    def delete_assignment(self, assignment: OnboardingTraining) -> None:
        self.db.delete(assignment)
        self.db.commit()

from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import SeasonRepository, UserRepository
from bot.database.models import SeasonParticipant, User


class RatingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.season_repo = SeasonRepository(session)
        self.user_repo = UserRepository(session)

    async def get_context(self, user: User, season_id: int) -> dict:
        """Returns user's rank, tickets, neighbors, and distance to next place."""
        sp = await self.season_repo.get_participant(user.id, season_id)
        if sp is None:
            return {
                "rank": 0,
                "tickets": 0,
                "prev": None,
                "next": None,
                "tickets_to_next": None,
            }

        rank = await self.season_repo.get_user_rank(user.id, season_id)
        board = await self.season_repo.get_leaderboard(season_id, limit=200)

        # Find neighbors
        board_with_rank = list(enumerate(board, start=1))
        user_idx = next((i for i, (r, p) in enumerate(board_with_rank) if p.user_id == user.id), None)

        prev_entry = board_with_rank[user_idx - 1] if user_idx and user_idx > 0 else None
        next_entry = board_with_rank[user_idx + 1] if user_idx is not None and user_idx + 1 < len(board_with_rank) else None

        prev_data = None
        if prev_entry:
            prev_rank, prev_sp = prev_entry
            prev_user = await self.user_repo.get_by_id(prev_sp.user_id)
            prev_data = {"rank": prev_rank, "name": prev_user.first_name if prev_user else "—", "tickets": prev_sp.tickets}

        next_data = None
        tickets_to_next = None
        if next_entry:
            next_rank, next_sp = next_entry
            next_user = await self.user_repo.get_by_id(next_sp.user_id)
            next_data = {"rank": next_rank, "name": next_user.first_name if next_user else "—", "tickets": next_sp.tickets}

        if prev_data:
            tickets_to_next = prev_data["tickets"] - sp.tickets

        return {
            "rank": rank,
            "tickets": sp.tickets,
            "prev": prev_data,
            "next": next_data,
            "tickets_to_next": max(0, tickets_to_next) if tickets_to_next is not None else None,
        }

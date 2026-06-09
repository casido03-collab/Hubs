from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, JSON, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=False, default="")
    age_range = Column(String(16), nullable=True)
    gender = Column(String(16), nullable=True)
    interests = Column(JSON, default=list)
    referral_code = Column(String(32), unique=True, nullable=False)
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_subscribed = Column(Boolean, default=False)
    login_streak = Column(Integer, default=0)
    last_login_date = Column(DateTime(timezone=True), nullable=True)
    last_bonus_date = Column(DateTime(timezone=True), nullable=True)
    registration_date = Column(DateTime(timezone=True), server_default=func.now())
    total_wins = Column(Integer, default=0)
    last_push_date = Column(DateTime(timezone=True), nullable=True)
    onboarding_done = Column(Boolean, default=False)

    season_participations = relationship("SeasonParticipant", back_populates="user")
    ticket_transactions = relationship("TicketTransaction", back_populates="user")
    wins = relationship("Winner", back_populates="user")


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True)
    number = Column(Integer, unique=True, nullable=False)
    name = Column(String(256), nullable=False)
    prize_name = Column(String(256), nullable=False)
    prize_photo_id = Column(String(256), nullable=True)
    sponsor_type = Column(String(16), nullable=False, default="channel")  # channel / bot
    sponsor_channel = Column(String(256), nullable=True)   # used when sponsor_type="channel"
    sponsor_channel_id = Column(BigInteger, nullable=True)
    sponsor_bot = Column(String(256), nullable=True)        # used when sponsor_type="bot"
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=False, index=True)
    status = Column(String(32), default="pending")  # pending / active / finished

    participants = relationship("SeasonParticipant", back_populates="season")
    mini_raffles = relationship("MiniRaffle", back_populates="season")
    winners = relationship("Winner", back_populates="season")


class SeasonParticipant(Base):
    __tablename__ = "season_participants"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    tickets = Column(Integer, default=0)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="season_participations")
    season = relationship("Season", back_populates="participants")


class TicketTransaction(Base):
    __tablename__ = "ticket_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="ticket_transactions")


class MiniRaffle(Base):
    __tablename__ = "mini_raffles"

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    day_number = Column(Integer, nullable=False)
    prize_amount = Column(Integer, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    conducted_at = Column(DateTime(timezone=True), nullable=True)
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(32), default="scheduled")  # scheduled / pending_admin / done

    season = relationship("Season", back_populates="mini_raffles")
    winner = relationship("User", foreign_keys=[winner_id])


class Winner(Base):
    __tablename__ = "winners"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    raffle_type = Column(String(16), nullable=False)  # mini / main
    prize = Column(String(256), nullable=False)
    photo_id = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(32), default="pending")  # pending / published
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="wins")
    season = relationship("Season", back_populates="winners")


class PushLog(Base):
    __tablename__ = "push_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    push_type = Column(String(64), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())


class GlobalSetting(Base):
    __tablename__ = "global_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False, default="")

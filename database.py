from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, Float, Date
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import date

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'user_profile'
    id = Column(Integer, primary_key=True)
    name = Column(String, default="Scholar")
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    xp_required_for_next_level = Column(Integer, default=1000)

class Book(Base):
    __tablename__ = 'books'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    author = Column(String)
    total_pages = Column(Integer, nullable=False)
    pages_read = Column(Integer, default=0)
    
    exercises = relationship("Exercise", back_populates="book", cascade="all, delete-orphan")
    syntheses = relationship("Synthesis", back_populates="book")
    flashcards = relationship("Flashcard", back_populates="book")

class Exercise(Base):
    __tablename__ = 'exercises'
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id'))
    section = Column(String, nullable=False)
    number = Column(String, nullable=False)
    
    book = relationship("Book", back_populates="exercises")

class Synthesis(Base):
    __tablename__ = 'syntheses'
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id'))
    concept_name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    word_count = Column(Integer)
    xp_earned = Column(Integer)
    
    book = relationship("Book", back_populates="syntheses")

class Flashcard(Base):
    __tablename__ = 'flashcards'
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id'))
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    next_review = Column(Date, default=date.today)
    interval = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)

    book = relationship("Book", back_populates="flashcards")

# Database setup
engine = create_engine('sqlite:///orchestrator.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

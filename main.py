import sys
import math
import random
from datetime import date, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QProgressBar, QTabWidget, 
                             QLineEdit, QPushButton, QListWidget, QFormLayout, 
                             QComboBox, QTextEdit, QMessageBox, QGroupBox, QInputDialog, QDialog, QSplitter)
from PyQt6.QtCore import QTimer, Qt
import pyqtgraph as pg

from database import Session, UserProfile, Book, Synthesis, Flashcard, Exercise

class ExerciseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Specific Exercise")
        layout = QFormLayout(self)
        
        self.section_input = QLineEdit()
        self.section_input.setPlaceholderText("e.g., 2.4, Chapter 3, etc.")
        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("e.g., 15, 2a, etc.")
        
        layout.addRow("Section/Chapter:", self.section_input)
        layout.addRow("Exercise Number:", self.number_input)
        
        btn_layout = QHBoxLayout()
        submit_btn = QPushButton("Log Exercise")
        submit_btn.clicked.connect(self.accept)
        btn_layout.addWidget(submit_btn)
        layout.addRow(btn_layout)

    def get_data(self):
        return self.section_input.text().strip(), self.number_input.text().strip()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Personal Learning Orchestrator")
        self.setGeometry(100, 100, 1000, 800)
        
        self.ensure_user_profile()
        self.setup_ui()
        self.update_header()

    def ensure_user_profile(self):
        session = Session()
        user = session.query(UserProfile).first()
        if not user:
            user = UserProfile()
            session.add(user)
            session.commit()
        session.close()

    def add_xp(self, amount):
        session = Session()
        user = session.query(UserProfile).first()
        user.xp += amount
        
        leveled_up = False
        while user.xp >= user.xp_required_for_next_level:
            user.xp -= user.xp_required_for_next_level
            user.level += 1
            user.xp_required_for_next_level = int(user.xp_required_for_next_level * 1.2)
            leveled_up = True
            
        session.commit()
        session.close()
        self.update_header()
        
        if leveled_up:
            QMessageBox.information(self, "Level Up!", f"Congratulations! You've reached Level {user.level}!")

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header
        header_layout = QHBoxLayout()
        self.level_label = QLabel()
        self.level_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        self.xp_bar = QProgressBar()
        self.xp_bar.setTextVisible(True)
        header_layout.addWidget(self.level_label)
        header_layout.addWidget(self.xp_bar)
        main_layout.addLayout(header_layout)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.active_stack_tab = QWidget()
        self.forge_tab = QWidget()
        self.feynman_tab = QWidget()
        self.spaced_rep_tab = QWidget()
        self.analytics_tab = QWidget()

        self.tabs.addTab(self.active_stack_tab, "Active Stack")
        self.tabs.addTab(self.forge_tab, "The Forge")
        self.tabs.addTab(self.feynman_tab, "Feynman Synthesis")
        self.tabs.addTab(self.spaced_rep_tab, "Spaced Repetition")
        self.tabs.addTab(self.analytics_tab, "Analytics & Node View")

        self.setup_active_stack_tab()
        self.setup_forge_tab()
        self.setup_feynman_tab()
        self.setup_spaced_repetition_tab()
        self.setup_analytics_tab()
        
        self.tabs.currentChanged.connect(self.on_tab_change)

    def update_header(self):
        session = Session()
        user = session.query(UserProfile).first()
        self.level_label.setText(f"Level: {user.level}")
        self.xp_bar.setMaximum(user.xp_required_for_next_level)
        self.xp_bar.setValue(user.xp)
        self.xp_bar.setFormat(f"{user.xp} / {user.xp_required_for_next_level} XP")
        session.close()

    def on_tab_change(self):
        self.refresh_feynman_books()
        self.refresh_srs_books()
        self.load_due_flashcards()
        if self.tabs.currentWidget() == self.analytics_tab:
            self.refresh_analytics()

    # --- Active Stack Tab ---
    def setup_active_stack_tab(self):
        layout = QVBoxLayout(self.active_stack_tab)
        
        self.book_list = QListWidget()
        self.load_books()
        layout.addWidget(self.book_list)

        btn_layout = QHBoxLayout()
        update_progress_btn = QPushButton("Update Pages Read")
        update_progress_btn.clicked.connect(self.update_book_progress)
        
        log_exercise_btn = QPushButton("Log Specific Exercise")
        log_exercise_btn.clicked.connect(self.log_book_exercise)

        btn_layout.addWidget(update_progress_btn)
        btn_layout.addWidget(log_exercise_btn)
        layout.addLayout(btn_layout)

        add_group = QGroupBox("Add New Book")
        form_layout = QFormLayout()
        self.book_title_input = QLineEdit()
        self.book_author_input = QLineEdit()
        self.book_pages_input = QLineEdit()
        form_layout.addRow("Title:", self.book_title_input)
        form_layout.addRow("Author:", self.book_author_input)
        form_layout.addRow("Total Pages:", self.book_pages_input)
        
        add_book_btn = QPushButton("Add to Stack")
        add_book_btn.clicked.connect(self.add_book)
        form_layout.addRow(add_book_btn)
        add_group.setLayout(form_layout)
        layout.addWidget(add_group)

    def load_books(self):
        self.book_list.clear()
        session = Session()
        for book in session.query(Book).all():
            progress = (book.pages_read / book.total_pages) * 100 if book.total_pages > 0 else 0
            exercise_count = len(book.exercises)
            item_text = f"[{book.id}] {book.title} - {book.pages_read}/{book.total_pages} pages ({progress:.1f}%) | Exercises Logged: {exercise_count}"
            self.book_list.addItem(item_text)
        session.close()

    def add_book(self):
        title, author, pages = self.book_title_input.text(), self.book_author_input.text(), self.book_pages_input.text()
        if title and pages.isdigit():
            session = Session()
            session.add(Book(title=title, author=author, total_pages=int(pages)))
            session.commit()
            session.close()
            self.load_books()
            self.book_title_input.clear(); self.book_author_input.clear(); self.book_pages_input.clear()

    def update_book_progress(self):
        selected = self.book_list.currentItem()
        if not selected: return
        book_id = int(selected.text().split(']')[0][1:])
        
        pages, ok = QInputDialog.getInt(self, "Update Progress", "Total pages read so far:", 0, 0, 10000)
        if ok:
            session = Session()
            book = session.query(Book).get(book_id)
            if book:
                pages_read_now = pages - book.pages_read
                book.pages_read = min(pages, book.total_pages)
                session.commit()
                if pages_read_now > 0:
                    self.add_xp(pages_read_now * 5)
            session.close()
            self.load_books()

    def log_book_exercise(self):
        selected = self.book_list.currentItem()
        if not selected: return
        book_id = int(selected.text().split(']')[0][1:])
        
        dialog = ExerciseDialog(self)
        if dialog.exec():
            section, number = dialog.get_data()
            if section and number:
                session = Session()
                existing = session.query(Exercise).filter_by(book_id=book_id, section=section, number=number).first()
                if not existing:
                    session.add(Exercise(book_id=book_id, section=section, number=number))
                    session.commit()
                    self.add_xp(15) 
                    QMessageBox.information(self, "Exercise Logged", f"Logged Exercise {number} in Section {section}! +15 XP")
                else:
                    QMessageBox.warning(self, "Duplicate", "You have already logged this specific exercise.")
                session.close()
                self.load_books()

    # --- The Forge Tab ---
    def setup_forge_tab(self):
        layout = QVBoxLayout(self.forge_tab)
        
        self.time_left = 90 * 60
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_tick)
        
        self.timer_label = QLabel(self.format_time(self.time_left))
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setStyleSheet("font-size: 64px; font-weight: bold;")
        layout.addWidget(self.timer_label)

        controls_layout = QHBoxLayout()
        self.start_pause_btn = QPushButton("Start Deep Work")
        self.start_pause_btn.clicked.connect(self.toggle_timer)
        self.eureka_btn = QPushButton("Eureka! (Solved Hard Problem)")
        self.eureka_btn.setStyleSheet("background-color: gold; color: black; font-weight: bold;")
        self.eureka_btn.clicked.connect(self.eureka_moment)
        
        controls_layout.addWidget(self.start_pause_btn)
        controls_layout.addWidget(self.eureka_btn)
        layout.addLayout(controls_layout)

    def format_time(self, seconds):
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def toggle_timer(self):
        if self.timer.isActive():
            self.timer.stop()
            self.start_pause_btn.setText("Resume Deep Work")
        else:
            self.timer.start(1000)
            self.start_pause_btn.setText("Pause")

    def timer_tick(self):
        self.time_left -= 1
        self.timer_label.setText(self.format_time(self.time_left))
        if self.time_left <= 0:
            self.timer.stop()
            self.add_xp(500)
            QMessageBox.information(self, "Session Complete", "90 minutes of Deep Work completed! +500 XP")
            self.time_left = 90 * 60
            self.timer_label.setText(self.format_time(self.time_left))
            self.start_pause_btn.setText("Start Deep Work")

    def eureka_moment(self):
        session = Session()
        user = session.query(UserProfile).first()
        reward = max(1, user.xp_required_for_next_level // 25)
        session.close()
        self.add_xp(reward)
        QMessageBox.information(self, "Eureka!", f"Brilliant insight! +{reward} XP.")

    # --- Feynman Synthesis Tab ---
    def setup_feynman_tab(self):
        layout = QVBoxLayout(self.feynman_tab)
        form_layout = QFormLayout()
        
        self.feynman_book_combo = QComboBox()
        self.concept_input = QLineEdit()
        self.concept_input.setPlaceholderText("e.g., Use $$...$$ for math formulas")
        
        form_layout.addRow("Related Book:", self.feynman_book_combo)
        form_layout.addRow("Concept:", self.concept_input)
        layout.addLayout(form_layout)

        self.synthesis_text = QTextEdit()
        self.synthesis_text.setPlaceholderText("Explain simply. Use $$x^2$$ for math...")
        layout.addWidget(self.synthesis_text)

        submit_btn = QPushButton("Publish Synthesis")
        submit_btn.clicked.connect(self.submit_synthesis)
        layout.addWidget(submit_btn)

    def refresh_feynman_books(self):
        self.feynman_book_combo.clear()
        self.feynman_book_combo.addItem("None (General)")
        session = Session()
        for book in session.query(Book).all():
            self.feynman_book_combo.addItem(book.title, userData=book.id)
        session.close()

    def submit_synthesis(self):
        concept, content = self.concept_input.text().strip(), self.synthesis_text.toPlainText().strip()
        if not concept or not content: return
        
        word_count = len(content.split())
        xp_earned = 50 + (word_count // 10) 

        session = Session()
        book_id = self.feynman_book_combo.currentData() if self.feynman_book_combo.currentIndex() > 0 else None
        session.add(Synthesis(book_id=book_id, concept_name=concept, content=content, word_count=word_count, xp_earned=xp_earned))
        session.commit()
        session.close()

        self.add_xp(xp_earned)
        self.concept_input.clear(); self.synthesis_text.clear()
        QMessageBox.information(self, "Success", f"Synthesis saved! +{xp_earned} XP.")

    # --- Spaced Repetition Tab ---
    def setup_spaced_repetition_tab(self):
        layout = QVBoxLayout(self.spaced_rep_tab)
        
        add_group = QGroupBox("Create Flashcard")
        add_layout = QFormLayout()
        self.srs_book_combo = QComboBox()
        self.front_input = QTextEdit()
        self.front_input.setFixedHeight(50)
        self.back_input = QTextEdit()
        self.back_input.setFixedHeight(50)
        
        add_btn = QPushButton("Add Card")
        add_btn.clicked.connect(self.add_flashcard)
        
        add_layout.addRow("Book:", self.srs_book_combo)
        add_layout.addRow("Front:", self.front_input)
        add_layout.addRow("Back:", self.back_input)
        add_layout.addRow(add_btn)
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        review_group = QGroupBox("Review Due Cards")
        review_layout = QVBoxLayout()
        
        self.review_label = QLabel("No cards due today.")
        self.review_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.review_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 20px;")
        review_layout.addWidget(self.review_label)
        
        self.show_answer_btn = QPushButton("Show Answer")
        self.show_answer_btn.clicked.connect(self.show_answer)
        self.show_answer_btn.hide()
        review_layout.addWidget(self.show_answer_btn)

        self.rating_layout = QHBoxLayout()
        self.hard_btn = QPushButton("Hard (Soon)")
        self.good_btn = QPushButton("Good")
        self.easy_btn = QPushButton("Easy")
        
        self.hard_btn.clicked.connect(lambda: self.process_review(0))
        self.good_btn.clicked.connect(lambda: self.process_review(1))
        self.easy_btn.clicked.connect(lambda: self.process_review(2))
        
        self.rating_layout.addWidget(self.hard_btn)
        self.rating_layout.addWidget(self.good_btn)
        self.rating_layout.addWidget(self.easy_btn)
        
        self.rating_widget = QWidget()
        self.rating_widget.setLayout(self.rating_layout)
        self.rating_widget.hide()
        review_layout.addWidget(self.rating_widget)
        
        review_group.setLayout(review_layout)
        layout.addWidget(review_group)
        
        self.current_card = None

    def refresh_srs_books(self):
        self.srs_book_combo.clear()
        self.srs_book_combo.addItem("None (General)")
        session = Session()
        for book in session.query(Book).all():
            self.srs_book_combo.addItem(book.title, userData=book.id)
        session.close()

    def add_flashcard(self):
        front, back = self.front_input.toPlainText().strip(), self.back_input.toPlainText().strip()
        if not front or not back: return
        
        session = Session()
        book_id = self.srs_book_combo.currentData() if self.srs_book_combo.currentIndex() > 0 else None
        session.add(Flashcard(book_id=book_id, front=front, back=back))
        session.commit()
        session.close()
        
        self.front_input.clear(); self.back_input.clear()
        self.add_xp(10) 
        self.load_due_flashcards()

    def load_due_flashcards(self):
        session = Session()
        self.due_cards = session.query(Flashcard).filter(Flashcard.next_review <= date.today()).all()
        session.close()
        self.next_card()

    def next_card(self):
        self.rating_widget.hide()
        if not self.due_cards:
            self.review_label.setText("All caught up! No cards due.")
            self.show_answer_btn.hide()
            self.current_card = None
            return
            
        self.current_card = self.due_cards[0]
        self.review_label.setText(f"Q: {self.current_card.front}")
        self.show_answer_btn.show()

    def show_answer(self):
        if not self.current_card: return
        self.review_label.setText(f"Q: {self.current_card.front}\n\nA: {self.current_card.back}")
        self.show_answer_btn.hide()
        self.rating_widget.show()

    def process_review(self, quality):
        if not self.current_card: return
        
        session = Session()
        card = session.query(Flashcard).get(self.current_card.id)
        
        if quality == 0:
            card.interval = 1
            card.ease_factor = max(1.3, card.ease_factor - 0.2)
        elif quality == 1:
            card.interval = 3 if card.interval == 0 else int(card.interval * card.ease_factor)
        else:
            card.ease_factor += 0.15
            card.interval = 4 if card.interval == 0 else int(card.interval * card.ease_factor * 1.3)
            
        card.next_review = date.today() + timedelta(days=card.interval)
        session.commit()
        session.close()
        
        self.add_xp(15) 
        self.due_cards.pop(0)
        self.next_card()

    # --- Analytics & Node View Tab ---
    def setup_analytics_tab(self):
        layout = QVBoxLayout(self.analytics_tab)
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top: Progress Graph
        self.progress_plot = pg.PlotWidget(title="Book Completion Progress (%)")
        self.progress_plot.setLabel('left', 'Completion Percentage')
        self.progress_plot.setLabel('bottom', 'Books')
        self.progress_plot.setYRange(0, 100)
        splitter.addWidget(self.progress_plot)

        # Bottom: Node View
        self.node_view = pg.PlotWidget(title="Knowledge Graph (Books & Syntheses)")
        self.node_view.hideAxis('bottom')
        self.node_view.hideAxis('left')
        splitter.addWidget(self.node_view)
        
        layout.addWidget(splitter)

    def refresh_analytics(self):
        session = Session()
        books = session.query(Book).all()
        
        # Refresh Bar Chart
        self.progress_plot.clear()
        x_dict = dict(enumerate([b.title for b in books]))
        
        if books:
            y_data = [(b.pages_read / b.total_pages) * 100 if b.total_pages > 0 else 0 for b in books]
            x_data = list(range(len(books)))
            
            bar_item = pg.BarGraphItem(x=x_data, height=y_data, width=0.6, brush='b')
            self.progress_plot.addItem(bar_item)
            
            ax = self.progress_plot.getAxis('bottom')
            ax.setTicks([list(x_dict.items())])
        
        # Refresh Node View
        self.node_view.clear()
        if not books:
            session.close()
            return

        book_points = []
        synth_points = []
        lines = []

        # Generate positions (Circle for books, branches for syntheses)
        radius = 10
        for i, book in enumerate(books):
            angle = (2 * math.pi * i) / len(books)
            bx, by = radius * math.cos(angle), radius * math.sin(angle)
            book_points.append({'pos': (bx, by), 'data': book.title, 'brush': pg.mkBrush('r')})
            
            # Sub-nodes (Syntheses)
            syntheses = book.syntheses
            for j, synth in enumerate(syntheses):
                s_angle = angle + (random.uniform(-0.5, 0.5))
                sx, sy = bx + 4 * math.cos(s_angle), by + 4 * math.sin(s_angle)
                synth_points.append({'pos': (sx, sy), 'data': synth.concept_name, 'brush': pg.mkBrush('g')})
                
                # Draw edge
                line = pg.PlotDataItem([bx, sx], [by, sy], pen=pg.mkPen('w', width=1))
                self.node_view.addItem(line)

        # Add Nodes (Scatter Plot)
        scatter = pg.ScatterPlotItem(size=15, pen=pg.mkPen(None), hoverable=True, hoverSymbol='s', hoverSize=20)
        scatter.addPoints(book_points + synth_points)
        self.node_view.addItem(scatter)

        session.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())  

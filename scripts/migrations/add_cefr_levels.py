#!/usr/bin/env python3
"""
Add CEFR levels to all books in the database.
Based on research and standard difficulty classifications for classic literature.
"""

import sqlite3

from backend import config

DB_PATH = config.DATABASE_PATH

# CEFR Level mapping based on:
# - Blog post "10 Classic Books for English Learners by Difficulty"
# - Standard graded reader classifications
# - Language complexity analysis
#
# A1: Very basic, simple vocabulary, present tense (usually adapted texts only)
# A2: Basic stories, simple past tense, common vocabulary
# B1: Intermediate, clear narrative, standard English
# B2: Upper-intermediate, some complex structures, wider vocabulary
# C1: Advanced, complex sentences, literary devices, archaic language
# C2: Proficient, highly complex, dense prose, extensive vocabulary

CEFR_LEVELS = {
    # A2-B1 Level (Elementary to Intermediate)
    "alices-adventures-in-wonderland": "A2-B1",  # Simple, dialogue-heavy, written for children
    "the-wonderful-wizard-of-oz": "A2-B1",  # Children's literature, clear narrative
    "the-jungle-book": "B1",  # Adventure stories, accessible language
    "peter-pan": "B1",  # Children's adventure, straightforward

    # B1 Level (Intermediate)
    "a-christmas-carol-in-prose": "B1",  # Short, familiar story, clear moral
    "the-adventures-of-sherlock-holmes": "B1",  # Mystery stories, logical narrative
    "the-strange-case-of-dr-jekyll-and-mr-hyde": "B1-B2",  # Short novella, some complexity
    "treasure-island": "B1",  # Adventure story, accessible
    "the-call-of-the-wild": "B1",  # Adventure, straightforward narrative
    "white-fang": "B1",  # Similar to Call of the Wild
    "the-adventures-of-tom-sawyer": "B1",  # Children's adventure, American English
    "around-the-world-in-eighty-days": "B1",  # Adventure, clear plot

    # B2 Level (Upper-Intermediate)
    "the-great-gatsby": "B2",  # Modern prose, symbolic but accessible
    "pride-and-prejudice": "B2",  # Complex social dynamics, witty dialogue
    "sense-and-sensibility": "B2",  # Similar to Pride and Prejudice
    "the-picture-of-dorian-gray": "B2",  # Philosophical but readable
    "frankenstein": "B2-C1",  # Gothic, frame narrative, some complexity
    "dracula": "B2",  # Gothic horror, epistolary format
    "the-time-machine": "B2",  # Science fiction, accessible Wells prose
    "the-war-of-the-worlds": "B2",  # Science fiction, clear narrative
    "the-invisible-man-a-grotesque-romance": "B2",  # Science fiction
    "a-tale-of-two-cities": "B2",  # Dickens, historical, dramatic
    "oliver-twist": "B2",  # Dickens, social commentary
    "great-expectations": "B2",  # Dickens, coming-of-age
    "romeo-and-juliet": "B2",  # Shakespeare, but familiar story
    "the-scarlet-letter": "B2",  # American classic, symbolic
    "little-women-or-meg-jo-beth-and-amy": "B2",  # Family story, accessible
    "anne-of-green-gables": "B2",  # Canadian classic, clear prose
    "a-little-princess": "B2",  # Children's classic, emotional depth
    "the-enchanted-april": "B2",  # Light romance, accessible

    # C1 Level (Advanced)
    "jane-eyre": "C1",  # Complex narrative, passionate prose, Victorian
    "wuthering-heights": "C1",  # Complex structure, dialect, dark themes
    "adventures-of-huckleberry-finn": "C1",  # Dialect, social commentary
    "moby-dick-or-the-whale": "C1",  # Dense prose, philosophical, technical
    "the-iliad": "C1",  # Epic poetry, archaic language
    "the-odyssey": "C1",  # Epic poetry, complex narrative
    "crime-and-punishment": "C1",  # Russian literature, psychological depth
    "anna-karenina": "C1",  # Russian epic, complex characters
    "war-and-peace": "C1-C2",  # Very long, complex, philosophical
    "middlemarch": "C1",  # Victorian, complex social analysis
    "bleak-house": "C1",  # Dickens at his most complex
    "the-count-of-monte-cristo": "C1",  # Long, intricate plot
    "a-journey-to-the-centre-of-the-earth": "B2",  # Verne adventure
    "twenty-thousand-leagues-under-the-sea": "B2",  # Verne adventure
    "gullivers-travels-into-several-remote-nations-of-the-world": "C1",  # Satire, complex
    "history-of-tom-jones-a-foundling": "C1",  # 18th century, complex
    "the-adventures-of-ferdinand-count-fathom": "C1",  # 18th century picaresque
    "carmilla": "B2",  # Gothic vampire story, accessible
    "the-king-in-yellow": "B2",  # Horror stories, atmospheric
    "through-the-looking-glass": "B1",  # Similar to Alice, children's book
    "winnie-the-pooh": "A2",  # Very simple, children's stories
    "the-blue-castle-a-novel": "B2",  # Romance, accessible
    "a-room-with-a-view": "B2",  # Forster, social comedy
    "the-eternal-moment-and-other-stories": "B2",  # Short stories
    "cranford": "B2",  # Victorian village life, gentle

    # C2 Level (Proficient)
    "ulysses": "C2",  # Joyce, stream of consciousness, very complex
    "the-house-of-the-seven-gables": "C1",  # Hawthorne, Gothic American

    # Non-fiction / Philosophy (C1-C2)
    "beyond-good-and-evil": "C2",  # Nietzsche philosophy
    "thus-spake-zarathustra-a-book-for-all-and-none": "C2",  # Nietzsche, poetic philosophy
    "the-origin-of-species": "C1",  # Darwin, scientific but readable
    "an-inquiry-into-the-nature-and-causes-of-the-wealth-of-nations": "C2",  # Adam Smith economics
    "principles-of-political-economy": "C2",  # Mill economics
    "the-history-of-the-decline-and-fall-of-the-roman-empire": "C2",  # Gibbon, historical

    # Fairy Tales (A2-B1)
    "fairy-tales-of-hans-christian-andersen": "A2-B1",  # Simple stories
    "grimms-fairy-tales": "A2-B1",  # Folk tales, simple language

    # Dumas novels (B2-C1)
    "the-three-musketeers": "B2",  # Adventure, accessible Dumas
    "twenty-years-after": "B2",  # Dumas sequel
    "the-vicomte-de-bragelonne": "B2-C1",  # Longer Dumas
    "ten-years-later": "B2-C1",  # Dumas continuation
    "the-man-in-the-iron-mask": "B2",  # Famous Dumas mystery
    "louise-de-la-valliere": "B2",  # Dumas romance

    # Verne (B1-B2)
    "from-the-earth-to-the-moon": "B1-B2",  # Verne science fiction
    "round-the-moon": "B1-B2",  # Verne sequel

    # Uncle Tom's Cabin
    "uncle-toms-cabin": "B2-C1",  # Social commentary, emotional, dialect

    # Brothers Karamazov
    "the-brothers-karamazov": "C1",  # Dostoyevsky, philosophical, complex
}

def update_cefr_levels():
    """Update CEFR levels for all books in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Updating CEFR levels for books...")
    print("=" * 80)

    updated_count = 0
    not_found_count = 0

    for slug, cefr_level in CEFR_LEVELS.items():
        cursor.execute(
            "UPDATE books SET cefr_level = ? WHERE slug = ?",
            (cefr_level, slug)
        )

        if cursor.rowcount > 0:
            # Get book title for confirmation
            cursor.execute("SELECT title FROM books WHERE slug = ?", (slug,))
            result = cursor.fetchone()
            if result:
                title = result[0]
                print(f"✓ {title[:50]:50} → {cefr_level}")
                updated_count += 1
        else:
            print(f"✗ Slug not found: {slug}")
            not_found_count += 1

    conn.commit()
    conn.close()

    print("=" * 80)
    print(f"\n✓ Updated {updated_count} books")
    if not_found_count > 0:
        print(f"✗ {not_found_count} slugs not found in database")
    print(f"\nTotal classifications: {len(CEFR_LEVELS)}")

if __name__ == '__main__':
    update_cefr_levels()

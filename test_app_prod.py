#!/usr/bin/env python3
"""Test script to verify app_prod.py works correctly"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

def test_imports():
    """Test that all imports work"""
    print("Testing imports...")
    try:
        from backend import app_prod
        print("✓ app_prod imported successfully")

        from backend import models
        print("✓ models imported successfully")

        from backend import config
        print("✓ config imported successfully")

        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_database_api():
    """Test database API calls"""
    print("\nTesting database API...")
    try:
        from backend import models
        db = models.Database()

        # Test get_all_books
        books = db.get_all_books()
        print(f"✓ db.get_all_books() returned {len(books)} books")

        if books:
            # Test get_book
            book_id = books[0]['id']
            book = db.get_book(book_id)
            print(f"✓ db.get_book({book_id}) returned: {book['title']}")

            # Test get_summary
            summary = db.get_summary(book_id, 'concise')
            if summary:
                print(f"✓ db.get_summary({book_id}, 'concise') returned {len(summary['content'])} chars")
            else:
                print(f"  No concise summary for book {book_id}")

            # Test get_chapters
            chapters = db.get_chapters(book_id)
            print(f"✓ db.get_chapters({book_id}) returned {len(chapters)} chapters")

        return True
    except Exception as e:
        print(f"✗ Database API failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_routes():
    """Test that app routes are defined"""
    print("\nTesting Flask app routes...")
    try:
        from backend.app_prod import app

        # Get list of routes
        routes = [str(rule) for rule in app.url_map.iter_rules()]
        print(f"✓ App has {len(routes)} routes defined:")
        for route in sorted(routes):
            print(f"  - {route}")

        # Check for expected routes
        expected_routes = ['/health', '/api/books', '/api/summary-configs']
        for route in expected_routes:
            if any(route in r for r in routes):
                print(f"✓ Route {route} exists")
            else:
                print(f"✗ Route {route} missing")

        return True
    except Exception as e:
        print(f"✗ App route test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("="*60)
    print("Testing app_prod.py")
    print("="*60)

    success = True
    success &= test_imports()
    success &= test_database_api()
    success &= test_app_routes()

    print("\n" + "="*60)
    if success:
        print("✓ All tests passed!")
        print("✓ app_prod.py is ready for deployment")
    else:
        print("✗ Some tests failed")
        sys.exit(1)
    print("="*60)

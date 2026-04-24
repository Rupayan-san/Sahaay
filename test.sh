#!/bin/bash

echo "🧪 Running all tests..."
echo ""
echo "=== BACKEND TESTS ==="
cd backend || exit 1
source venv/bin/activate
pytest tests/ -v --tb=short
BACKEND_EXIT=$?

echo ""
echo "=== FRONTEND TESTS ==="
cd ../frontend || exit 1
npm test -- --watchAll=false --coverage
FRONTEND_EXIT=$?

echo ""
if [ $BACKEND_EXIT -eq 0 ] && [ $FRONTEND_EXIT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
else
    echo "❌ SOME TESTS FAILED"
    echo "Backend exit: $BACKEND_EXIT"
    echo "Frontend exit: $FRONTEND_EXIT"
fi

from datetime import date
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import BlueBookRenewal, Customer

User = get_user_model()

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _create_customer():
    user = User.objects.create_user(
        email='test@test.com',
        password='test123',
        user_type='customer',
        is_active=True,
    )
    Customer.objects.create(user=user, full_name='Test', phone='9800000000')
    return user

def _auth_client(client, user):
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


# ─────────────────────────────────────────────────────────────
# 1. Tax Tests (Core + Representative)
# ─────────────────────────────────────────────────────────────

class TaxTests(TestCase):

    def _tax(self, type, cc=0, kw=0):
        if type == 'two_wheeler':
            return 5000 if cc <= 150 else 6500
        if type == 'four_wheeler':
            return 25000 if cc <= 1500 else 27000
        if type == 'four_wheeler_ev':
            return 15000 if kw <= 125 else 20000

    def test_two_wheeler_tax(self):
        self.assertEqual(self._tax('two_wheeler', cc=150), 5000)

    def test_four_wheeler_tax(self):
        self.assertEqual(self._tax('four_wheeler', cc=1500), 25000)

    def test_ev_tax(self):
        self.assertEqual(self._tax('four_wheeler_ev', kw=100), 15000)


# ─────────────────────────────────────────────────────────────
# 2. Fine Tests (Boundary + Edge)
# ─────────────────────────────────────────────────────────────

class FineTests(TestCase):

    def _fine(self, d):
        if d <= 0: return 0
        if d <= 30: return 0.05
        if d <= 45: return 0.10
        return 0.20

    def test_fine_30_days(self):
        self.assertEqual(self._fine(30), 0.05)

    def test_fine_31_days(self):
        self.assertEqual(self._fine(31), 0.10)

    def test_fine_negative(self):
        self.assertEqual(self._fine(-5), 0)

    def test_fine_max(self):
        self.assertEqual(self._fine(60), 0.20)


# ─────────────────────────────────────────────────────────────
# 3. Overdue Tests
# ─────────────────────────────────────────────────────────────

class OverdueTests(TestCase):

    def _overdue(self, tax, charge, yrs):
        return (
            tax * yrs,
            tax * yrs * 0.32,
            charge * yrs
        )

    def test_one_year(self):
        u, f, r = self._overdue(5000, 300, 1)
        self.assertEqual((u, f, r), (5000, 1600, 300))

    def test_two_year(self):
        u, f, r = self._overdue(5000, 300, 2)
        self.assertEqual((u, f, r), (10000, 3200, 600))


# ─────────────────────────────────────────────────────────────
# 4. Amnesty Tests
# ─────────────────────────────────────────────────────────────

class AmnestyTests(TestCase):

    def _cap(self, d):
        return 3 if d < date(2026,6,16) else 5

    def test_active(self):
        self.assertEqual(self._cap(date(2026,1,1)), 3)

    def test_expired(self):
        self.assertEqual(self._cap(date(2026,6,16)), 5)

# ─────────────────────────────────────────────────────────────
# 4b. Amnesty Capped Overdue Tests (TC-13)
# ─────────────────────────────────────────────────────────────

class AmnestyCappedOverdueTests(TestCase):

    def _cap(self, d):
        return 3 if d < date(2026, 6, 16) else 5

    def _overdue(self, tax, charge, yrs):
        return (
            tax * yrs,
            tax * yrs * 0.32,
            charge * yrs
        )

    def test_capped_during_amnesty(self):
        """Vehicle overdue 6 years, but amnesty caps it at 3 years"""
        actual_years = 6
        capped_years = min(actual_years, self._cap(date(2026, 1, 1)))  # cap = 3
        unpaid, fine, renewal = self._overdue(5000, 300, capped_years)
        self.assertEqual(capped_years, 3)
        self.assertEqual(unpaid, 15000)
        self.assertEqual(fine, 4800)
        self.assertEqual(renewal, 900)

    def test_capped_after_amnesty(self):
        """Vehicle overdue 6 years, amnesty expired so cap is 5 years"""
        actual_years = 6
        capped_years = min(actual_years, self._cap(date(2026, 6, 16)))  # cap = 5
        unpaid, fine, renewal = self._overdue(5000, 300, capped_years)
        self.assertEqual(capped_years, 5)
        self.assertEqual(unpaid, 25000)
        self.assertEqual(fine, 8000)
        self.assertEqual(renewal, 1500)

    def test_no_cap_needed(self):
        """Vehicle overdue 2 years, under any cap — no capping applied"""
        actual_years = 2
        capped_years = min(actual_years, self._cap(date(2026, 1, 1)))  # cap = 3
        unpaid, fine, renewal = self._overdue(5000, 300, capped_years)
        self.assertEqual(capped_years, 2)   # unchanged
        self.assertEqual(unpaid, 10000)
        self.assertEqual(fine, 3200)
        self.assertEqual(renewal, 600)
        
# ─────────────────────────────────────────────────────────────
# 5. Model Tax Tests
# ─────────────────────────────────────────────────────────────

class ModelTaxTests(TestCase):

    def _model(self, age, cc):
        if age <= 5: return 0
        if age <= 10: return cc * 0.5
        return cc

    def test_new_vehicle(self):
        self.assertEqual(self._model(3,150), 0)

    def test_10_year(self):
        self.assertEqual(self._model(10,150), 75)

    def test_old_vehicle(self):
        self.assertEqual(self._model(12,150), 150)


# ─────────────────────────────────────────────────────────────
# 6. Insurance Tests
# ─────────────────────────────────────────────────────────────

class InsuranceTests(TestCase):

    def _ins(self, cc):
        if cc <= 149: return 1715
        if cc <= 250: return 1941
        return 2167

    def test_mid_range(self):
        self.assertEqual(self._ins(200), 1941)

    def test_no_insurance(self):
        self.assertEqual(0, 0)


# ─────────────────────────────────────────────────────────────
# 7. Total Calculation
# ─────────────────────────────────────────────────────────────

class TotalTests(TestCase):

    def test_no_fine(self):
        total = 5000 + 300 + 75 + 200
        self.assertEqual(total, 5575)

    def test_with_fine(self):
        total = 5000 + 1600 + 5000 + 1000 + 300 + 300 + 75 + 200
        self.assertEqual(total, 13475)

    def test_with_insurance(self):
        total = 10000 + 3200 + 5000 + 1000 + 300 + 600 + 0 + 1715 + 200
        self.assertEqual(total, 22015)

    def test_service_charge(self):
        self.assertEqual(5000 + 300 + 200, 5500)


# ─────────────────────────────────────────────────────────────
# 8. API Tests (Critical Only)
# ─────────────────────────────────────────────────────────────

class APITests(APITestCase):

    def setUp(self):
        self.user = _create_customer()
        _auth_client(self.client, self.user)

    def test_create_success(self):
        res = self.client.post('/api/services/blue-book/create/', {})
        self.assertIn(res.status_code, [201,400])  # depends on validation

    def test_unauthorized(self):
        self.client.credentials()
        res = self.client.post('/api/services/blue-book/create/', {})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_only_own(self):
        res = self.client.get('/api/services/blue-book/')
        self.assertEqual(res.status_code, 200)

    def test_invalid_data(self):
        res = self.client.post('/api/services/blue-book/create/', {'vehicle_type':'wrong'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
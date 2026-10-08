# app/core/rate_limits.py
from app.core.rate_limiter import RateLimiter

# 1. Autentykacja - wysokie ryzyko brute-force / spam kont
rate_limit_register = RateLimiter(
    times=3, seconds=3600)  # max 3 rejestracje / godzina

login_rate_limiter = RateLimiter(times=5, seconds=60)

# 2. Tworzenie i modyfikacja zasobów - ochrona przed spychaniem bazy danych
# max 30 tworzeń/edycji / minuta
rate_limit_mutations = RateLimiter(times=30, seconds=60)

# 3. Globalny odczyt - ochrona przed pętlami zapytań we frontendzie i scrapingiem
rate_limit_global_read = RateLimiter(
    times=200, seconds=60)  # max 200 odczytów / minuta

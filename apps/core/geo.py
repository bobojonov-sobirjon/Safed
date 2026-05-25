"""GPS koordinatalar uchun umumiy DecimalField parametrlari."""

# Oldin: max_digits=10, decimal_places=7
# Hozir: 18 kasr (mobil GPS to‘liq aniqlik)
GEO_COORD_MAX_DIGITS = 21
GEO_COORD_DECIMAL_PLACES = 18

def calculate_pet_years(human_years):
    if human_years == 1:
        cat_years = 15
        dog_years = 15
    elif human_years == 2:
        cat_years = 15 + 9  # 24
        dog_years = 15 + 9  # 24
    else:
        cat_years = 15 + 9 + (human_years - 2) * 4
        dog_years = 15 + 9 + (human_years - 2) * 5

    return [human_years, cat_years, dog_years]
print(calculate_pet_years(1))
print(calculate_pet_years(2))
print(calculate_pet_years(10))


# --- Testing with example values ---
test_cases = [1, 2, 10]

for human_years in test_cases:
    result = calculate_pet_years(human_years)
    print(f"human_years = {human_years} # output: {result}")
    
# 1. Print out all values one by one
for num in [1, 2, 3, 4]:
    print(num)

# 2. Print out all values multiplied by 20
for num in [1, 2, 3, 4]:
    print(num * 20)

# 3. Return a new list with only the first letter of each name
names = ["Elie", "Tim", "Matt"]
first_letters = [name[0] for name in names]
print(first_letters)  # Output: ['E', 'T', 'M']

# 4. Return a new list with all even values
numbers = [1, 2, 3, 4, 5, 6]
evens = [num for num in numbers if num % 2 == 0]
print(evens)  # Output: [2, 4, 6]

# 5. Return a new list with values present in both lists
list1 = [1, 2, 3, 4]
list2 = [3, 4, 5, 6]
common_values = [val for val in list1 if val in list2]
print(common_values)  # Output: [3, 4]

# 6. Return a new list with each word reversed and in lowercase
words = ["Elie", "Tim", "Matt"]
reversed_words = [word[::-1].lower() for word in words]
print(reversed_words)  # Output: ['eile', 'mit', 'ttam']

# 7. Return a new list of letters present in both strings
str1 = "first"
str2 = "third"
common_letters = [char for char in str1 if char in str2]
print(common_letters)  # Output: ['i', 'r', 't']

# 8. Return numbers between 1 and 100 divisible by 12
divisible_by_12 = [num for num in range(1, 101) if num % 12 == 0]
print(divisible_by_12)  # Output: [12, 24, 36, 48, 60, 72, 84, 96]

# 9. Return a list with all vowels removed from "amazing"
word = "amazing"
no_vowels = [char for char in word if char not in "aeiou"]
print(no_vowels)  # Output: ['m', 'z', 'n', 'g']

# 10. Generate a 3x3 list containing [0, 1, 2]
grid_3x3 = [[i for i in range(3)] for _ in range(3)]
print(grid_3x3)  # Output: [[0, 1, 2], [0, 1, 2], [0, 1, 2]]

# 11. Generate a 10x10 list containing [0, 1, ..., 9]
grid_10x10 = [[i for i in range(10)] for _ in range(10)]
print(grid_10x10)  # Output: [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], ..., [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]
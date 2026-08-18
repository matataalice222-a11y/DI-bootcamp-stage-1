# Exercise 1: Add Two Numbers
def add_two_numbers(a, b):
    return a + b

print(add_two_numbers(3, 5))  # Example usage


# Exercise 2: Print a Greeting
def greet(name):
    print(f"Hello, {name}!")
greet("Alice")  # Example usage

# Exercise 3: Check if Number is Even or Odd
def check_even_odd(number):
    if number % 2 == 0:
        print("Even")
        return "Even"
    else:
        print("Odd")
        return "Odd"

print(check_even_odd(4))  # Example usage
print(check_even_odd(7))  # Example usage
# Exercise 4: Sum of Numbers in a List
def sum_list(numbers):
    return sum(numbers)
print(sum_list([1, 2, 3, 4, 5])) 

 # Example usage


# Exercise 5: Print Days of the Week
def print_days():
    days = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    for day in days:
        print(day)
print_days()  # Example usage

# Exercise 6: Check if Number is Positive, Negative, or Zero
def check_sign(number):
    if number > 0:
        return "Positive"
    elif number < 0:
        print("Negative")
        return "Negative"
    else:
        print("Zero")
        return "Zero"


# Exercise 7: Repeat a Word
def repeat_word(word, count):
    for _ in range(count):
        print(word)
        
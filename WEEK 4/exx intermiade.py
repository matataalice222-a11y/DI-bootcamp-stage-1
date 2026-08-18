def find_largest(numbers):
    print("Finding the largest number in the list...")
    largest = numbers[0]
    for n in numbers:
        if n > largest:
            largest = n
    return largest

# Examples
print(find_largest([1, 2, 3, 4]))
print(find_largest([-1, -2, -3, -4]))
print(find_largest([10, 20, 5])) 
print(find_largest([100, 50, 75])) 
print(find_largest([100, 50, 75])) 
# Output: 100
#include <stdio.h>
#include <stdlib.h>

// Function to perform binary search on a sorted array
// Returns the index of the element if found, otherwise returns -1
int binarySearch(int arr[], int low, int high, int key) {
    if (low > high) {
        return -1; // Element not found
    }

    int mid = low + (high - low) / 2; // Calculate mid point to avoid overflow

    if (arr[mid] == key) {
        return mid; // Element found at mid index
    } else if (arr[mid] < key) {
        return binarySearch(arr, mid + 1, high, key); // Search in the right half
    } else {
        return binarySearch(arr, low, mid - 1, key); // Search in the left half
    }
}

// Function to perform recursive binary search with multiple occurrences
// Returns a pointer to an array of indices where the key is found
// The caller is responsible for freeing the returned array
int* binarySearchAll(int arr[], int low, int high, int key, int *count) {
    *count = 0;
    int* indices = NULL;
    int initial_mid = low + (high - low) / 2;

    if (low > high) {
        return NULL;
    }

    if (arr[initial_mid] == key) {
        // Found one occurrence, now search left and right for more
        indices = (int*)malloc(sizeof(int));
        indices[0] = initial_mid;
        (*count)++;

        // Search left
        int left_count = 0;
        int* left_indices = binarySearchAll(arr, low, initial_mid - 1, key, &left_count);
        if (left_indices != NULL) {
            indices = (int*)realloc(indices, sizeof(int) * (*count + left_count));
            for (int i = 0; i < left_count; ++i) {
                indices[*count + i] = left_indices[i];
            }
            *count += left_count;
            free(left_indices);
        }

        // Search right
        int right_count = 0;
        int* right_indices = binarySearchAll(arr, initial_mid + 1, high, key, &right_count);
        if (right_indices != NULL) {
            indices = (int*)realloc(indices, sizeof(int) * (*count + right_count));
            for (int i = 0; i < right_count; ++i) {
                indices[*count + i] = right_indices[i];
            }
            *count += right_count;
            free(right_indices);
        }
    } else if (arr[initial_mid] < key) {
        indices = binarySearchAll(arr, initial_mid + 1, high, key, count);
    } else {
        indices = binarySearchAll(arr, low, initial_mid - 1, key, count);
    }

    return indices;
}

// Function to perform iterative binary search
// Returns the index of the element if found, otherwise returns -1
int binarySearchIterative(int arr[], int n, int key) {
    int low = 0;
    int high = n - 1;

    while (low <= high) {
        int mid = low + (high - low) / 2;

        if (arr[mid] == key) {
            return mid; // Element found
        } else if (arr[mid] < key) {
            low = mid + 1; // Search in the right half
        } else {
            high = mid - 1; // Search in the left half
        }
    }

    return -1; // Element not found
}

int main() {
    int arr[] = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91, 91, 91, 99};
    int n = sizeof(arr) / sizeof(arr[0]);
    int key_to_find_single = 23;
    int key_to_find_multiple = 91;
    int key_not_present = 50;

    // --- Recursive Binary Search (single occurrence) ---
    printf("Recursive Binary Search (single occurrence):\n");
    int result_recursive = binarySearch(arr, 0, n - 1, key_to_find_single);
    if (result_recursive != -1) {
        printf("Element %d found at index %d\n", key_to_find_single, result_recursive);
    } else {
        printf("Element %d not found\n", key_to_find_single);
    }

    result_recursive = binarySearch(arr, 0, n - 1, key_not_present);
    if (result_recursive != -1) {
        printf("Element %d found at index %d\n", key_not_present, result_recursive);
    } else {
        printf("Element %d not found\n", key_not_present);
    }
    printf("\n");

    // --- Recursive Binary Search (all occurrences) ---
    printf("Recursive Binary Search (all occurrences):\n");
    int count_multiple = 0;
    int* indices_multiple = binarySearchAll(arr, 0, n - 1, key_to_find_multiple, &count_multiple);
    if (indices_multiple != NULL) {
        printf("Element %d found at indices: ", key_to_find_multiple);
        for (int i = 0; i < count_multiple; ++i) {
            printf("%d ", indices_multiple[i]);
        }
        printf("\n");
        free(indices_multiple); // Free allocated memory
    } else {
        printf("Element %d not found\n", key_to_find_multiple);
    }

    count_multiple = 0;
    indices_multiple = binarySearchAll(arr, 0, n - 1, key_not_present, &count_multiple);
    if (indices_multiple != NULL) {
        printf("Element %d found at indices: ", key_not_present);
        for (int i = 0; i < count_multiple; ++i) {
            printf("%d ", indices_multiple[i]);
        }
        printf("\n");
        free(indices_multiple);
    } else {
        printf("Element %d not found\n", key_not_present);
    }
    printf("\n");

    // --- Iterative Binary Search ---
    printf("Iterative Binary Search:\n");
    int result_iterative = binarySearchIterative(arr, n, key_to_find_single);
    if (result_iterative != -1) {
        printf("Element %d found at index %d\n", key_to_find_single, result_iterative);
    } else {
        printf("Element %d not found\n", key_to_find_single);
    }

    result_iterative = binarySearchIterative(arr, n, key_not_present);
    if (result_iterative != -1) {
        printf("Element %d found at index %d\n", key_not_present, result_iterative);
    } else {
        printf("Element %d not found\n", key_not_present);
    }
    printf("\n");

    return 0;
}
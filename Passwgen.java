Sure! Here's an example of a Java encryption function using the AES algorithm:

```java
import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public class EncryptionExample {

    private static final String KEY = "mysecretkey";

    public static String encrypt(String plaintext) throws Exception {
        SecretKeySpec secretKey = new SecretKeySpec(KEY.getBytes(), "AES");
        Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
        cipher.init(Cipher.ENCRYPT_MODE, secretKey);

        byte[] encryptedBytes = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
        return Base64.getEncoder().encodeToString(encryptedBytes);
    }

    public static String decrypt(String ciphertext) throws Exception {
        SecretKeySpec secretKey = new SecretKeySpec(KEY.getBytes(), "AES");
        Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
        cipher.init(Cipher.DECRYPT_MODE, secretKey);

        byte[] decryptedBytes = cipher.doFinal(Base64.getDecoder().decode(ciphertext));
        return new String(decryptedBytes, StandardCharsets.UTF_8);
    }

    public static void main(String[] args) {
        try {
            String plaintext = "Hello, World!";
            String encryptedText = encrypt(plaintext);
            System.out.println("Encrypted: " + encryptedText);

            String decryptedText = decrypt(encryptedText);
            System.out.println("Decrypted: " + decryptedText);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

In this example, the `encrypt` function takes a plaintext as input and returns the encrypted ciphertext. The `decrypt` function takes a ciphertext as input and returns the decrypted plaintext. The `KEY` variable represents the secret key used for encryption and decryption. The AES algorithm is used with ECB mode and PKCS5 padding. The `Base64` class is used to encode and decode the encrypted bytes.

You can modify the `plaintext` variable in the `main` method to encrypt and decrypt different messages.


To create a Base85 encoding function from scratch in Java, follow the steps below. Base85, also referred to as Ascii85, is a form of binary-to-text encoding that represents binary data in an ASCII format. It's more space-efficient than Base64. Note that this basic implementation focuses on the essence of Base85 encoding without delving into variants or encoding options that adjust the character set or handle padding differently.

Here's a straightforward example of implementing Base85 encoding:

```java
public class Base85Encoder {

    // The Base85 alphabet
    private static final String BASE85_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~";
    private static final int DIVISOR = 85;
    private static final int BLOCK_SIZE = 4;
    private static final int ENCODED_BLOCK_SIZE = 5;

    // Method to encode from bytes to a Base85 string
    public static String encode(byte[] data) {
        StringBuilder encoded = new StringBuilder();
        for (int i = 0; i < data.length; i += BLOCK_SIZE) {
            // Creating a long to handle the conversion (4 bytes => 1 long)
            long value = 0L;
            // This flag checks if the current block is the last one & might need padding
            boolean isLastBlock = i + BLOCK_SIZE >= data.length;
            int padding = 0;

            for (int j = 0; j < BLOCK_SIZE; j++) {
                value <<= 8;
                if (i + j < data.length) {
                    value |= (data[i + j] & 0xFF);
                } else {
                    padding++;
                }
            }

            // Encoding the block
            char[] encodedBlock = new char[ENCODED_BLOCK_SIZE];
            for (int j = ENCODED_BLOCK_SIZE - 1; j >= 0; j--) {
                encodedBlock[j] = BASE85_CHARS.charAt((int)(value % DIVISOR));
                value /= DIVISOR;
            }

            // Adding the encoded block to the result, adjusting for any necessary padding
            if (isLastBlock && padding > 0) {
                // Adjusting for padding - only add necessary chars
                for (int j = 0; j < encodedBlock.length - padding; j++) {
                    encoded.append(encodedBlock[j]);
                }
            } else {
                for (char c : encodedBlock) {
                    encoded.append(c);
                }
            }
        }
        return encoded.toString();
    }
}
```

### How to Use
You would use it like this:
```java
public class Main {
    public static void main(String[] args) {
        String testString = "Hello World!";
        byte[] bytes = testString.getBytes();
        String encoded = Base85Encoder.encode(bytes);
        System.out.println("Encoded text: " + encoded);
    }
}
```

### Notes
1. **Error Handling**: This example lacks detailed error handling and input validation, which should be added for robustness.
2. **Padding and Length**: The example simplifies handling the final block and its padding. Depending on how strict you need to adhere to a specific variant of Base85 encoding (such as Adobe's or ZeroMQ's versions), you might need to adjust padding handling.
3. **Performance**: If performance is critical, consider optimizing the conversion and encoding logic, especially if dealing with large data volumes.
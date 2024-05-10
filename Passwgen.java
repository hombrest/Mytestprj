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

 import java.security.SecureRandom;

public class Passwgen {

    private static final String UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    private static final String LOWER = "abcdefghijklmnopqrstuvwxyz";
    private static final String DIGITS = "0123456789";
    private static final String SPECIAL = "!@#$%^&*()_-+=";

    public static String generatePassword(int length) {
        String characters = UPPER + LOWER + DIGITS + SPECIAL;
        SecureRandom random = new SecureRandom();
        StringBuilder password = new StringBuilder();

        for (int i = 0; i < length; i++) {
            int randomIndex = random.nextInt(characters.length());
            password.append(characters.charAt(randomIndex));
        }

        return password.toString();
    }

    public static void main(String[] args) {
        int passwordLength = 10;
        String generatedPassword = generatePassword(passwordLength);
        System.out.println("Generated Password: " + generatedPassword);
    }
}
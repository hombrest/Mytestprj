# Generate the frequencies for notes in multiple octaves
notes <- c("A", "A#", "B", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#")
base_frequency <- 440  # A4
num_octaves <- 3
frequencies <- sapply(0:(12 * num_octaves - 1), function(x) base_frequency * 2^(x/12))
labels <- rep(notes, num_octaves)

# Plot the frequencies on a logarithmic scale
plot(frequencies, log = "y", type = "o", pch = 19, col = "blue", xaxt = "n",
     main = "Musical Note Frequencies", xlab = "Notes", ylab = "Frequency (Hz)")
axis(1, at = 1:length(frequencies), labels = labels, las = 2, cex.axis = 0.7)
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.ContentSummary;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;

/** Stable Hadoop 2/3 API instead of parsing version-dependent shell output. */
public final class StorageSummary {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("Expected one HDFS table location");
        }
        Path path = new Path(args[0]);
        try (FileSystem fs = path.getFileSystem(new Configuration())) {
            ContentSummary summary = fs.getContentSummary(path);
            System.out.printf("{\"logical_bytes\":%d,\"replicated_bytes\":%d}%n",
                summary.getLength(), summary.getSpaceConsumed());
        }
    }
}
